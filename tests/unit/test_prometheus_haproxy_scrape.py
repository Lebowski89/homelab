import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "ansible/roles/service_common/templates"


@pytest.mark.parametrize("runtime", ["docker", "podman"])
def test_shared_haproxy_job_preserves_both_instances_across_runtime_transition(runtime):
    env = Environment(loader=FileSystemLoader(TEMPLATES), undefined=StrictUndefined)
    rendered = env.get_template("configs/prometheus/haproxy-scrape.yml.j2").render(
        service_common_service={"runtime": runtime},
        prometheus_worker_metrics_address="192.0.2.20:22623",
        services_controller_host="manager",
        hostvars={"manager": {"local_ip": "192.0.2.48"}},
    )
    job = yaml.safe_load(rendered)[0]
    targets = [target for record in job["static_configs"] for target in record["targets"]]
    assert targets == ["192.0.2.48:18405", "haproxy:8405" if runtime == "docker" else "192.0.2.20:22623"]
    assert job["job_name"] == "haproxy" and job["metrics_path"] == "/metrics"
    instances = [record.get("labels", {}).get("instance", record["targets"][0]) for record in job["static_configs"]]
    assert instances == ["192.0.2.48:18405", "haproxy:8405"]


@pytest.mark.parametrize("failure", ["", "check", "promtool", "ambiguous", "mount", "labels", "replacement", "config", "reload"])
def test_actual_ansible_scrape_update_preserves_current_runtime_and_unrelated_configuration(tmp_path, failure):
    """Run the real task file using a local inventory and a daemon-free Docker executable."""
    config_dir = tmp_path / "prometheus"
    config_dir.mkdir()
    config_file = config_dir / "prometheus.yml"
    original = """# retained operator comment
global:
  scrape_interval: 30s
scrape_configs:
  - job_name: "before"
    static_configs:
      - targets: ["untouched-before:1111"]

  - job_name: "haproxy"
    scrape_interval: 15s
    metrics_path: /metrics
    scrape_timeout: 9s
    static_configs:
      - targets: ["haproxy:8405"]
        labels:
          retained: "existing-worker"

  - job_name: "after"
    static_configs:
      - targets: ["untouched-after:2222"]
"""
    if failure == "labels":
        original = original.replace(
            '\n  - job_name: "after"',
            '\n      - targets: ["192.0.2.48:18405"]\n        labels:\n          instance: wrong\n\n  - job_name: "after"',
        )
    config_file.write_text(original)
    (tmp_path / "loaded.yml").write_text(original)
    config_file.chmod(0o640)
    receipt = tmp_path / "docker-commands.jsonl"
    bindir = tmp_path / "bin"
    bindir.mkdir()
    docker = bindir / "docker"
    docker.write_text("""#!/usr/bin/python3
import json,os,sys
from pathlib import Path
import yaml
args=sys.argv[1:]
assert args[:2]==['--host','unix:///var/run/docker.sock']
args=args[2:]
root=Path(os.environ['SCRAPE_FIXTURE'])
failure=os.environ['SCRAPE_FAILURE']
with (root/'docker-commands.jsonl').open('a') as stream:stream.write(json.dumps(args)+'\\n')
identity='a'*64
if args[0]=='ps':
 assert 'label=com.docker.swarm.service.name=prometheus_prometheus' in args
 entries=[json.loads(line) for line in (root/'docker-commands.jsonl').read_text().splitlines()]
 print('b'*64 if failure=='replacement' and sum(entry[0]=='ps' for entry in entries)>1 else identity)
 if failure=='ambiguous':print('b'*64)
elif args[0]=='inspect':
 assert args[-1]==identity
 assert '.Config.Env' not in args[2]
 print(json.dumps({'id':identity,'pid':321,'managed_config':failure!='config','running':True,'service':'prometheus_prometheus',
  'mounts':[{'Type':'bind','Source':str(root/'prometheus'),'Destination':'/etc/prometheus','RW':failure=='mount'}]}))
elif args[:5]==['exec',identity,'/bin/promtool','check','config']:
 path=root/'prometheus'/Path(args[-1]).name
 cfg=yaml.safe_load(path.read_text())
 job=next(job for job in cfg['scrape_configs'] if job['job_name']=='haproxy')
 assert [target for record in job['static_configs'] for target in record['targets']]==['haproxy:8405','192.0.2.48:18405']
 if failure=='promtool':sys.exit(41)
elif args==['kill','--signal','HUP',identity]:
 if failure=='reload':sys.exit(53)
 (root/'loaded.yml').write_text((root/'prometheus/prometheus.yml').read_text())
else:raise SystemExit('unexpected runtime command')
""")
    docker.chmod(0o755)
    # The system Python runs this stub, so import YAML only from the already
    # available virtual environment; no install, socket or external command.
    docker.write_text(docker.read_text().replace("#!/usr/bin/python3", "#!" + sys.executable))
    nsenter = bindir / "nsenter"
    nsenter.write_text(
        "#!"
        + sys.executable
        + "\n"
        + """import json,os,sys
from pathlib import Path
assert sys.argv[1:6]==['--target','321','--net','/usr/bin/python3','-c']
compile(sys.argv[6],'<actual-status-query>','exec')
root=Path(os.environ['SCRAPE_FIXTURE'])
with (root/'docker-commands.jsonl').open('a') as stream:stream.write(json.dumps(['query'])+'\\n')
print((root/'loaded.yml').read_text())
"""
    )
    nsenter.chmod(0o755)
    (tmp_path / "roles/service_common").mkdir(parents=True)
    (tmp_path / "roles/service_common/templates").symlink_to(TEMPLATES, target_is_directory=True)
    inventory = tmp_path / "inventory.yml"
    inventory.write_text(
        yaml.safe_dump(
            {
                "all": {
                    "hosts": {
                        "manager": {"ansible_connection": "local", "ansible_python_interpreter": sys.executable, "local_ip": "192.0.2.48"}
                    }
                }
            }
        )
    )
    playbook = tmp_path / "playbook.yml"
    playbook.write_text(
        yaml.safe_dump(
            [
                {
                    "name": "Local real-task scrape regression",
                    "hosts": "manager",
                    "gather_facts": False,
                    "environment": {
                        "PATH": str(bindir) + ":/usr/bin:/bin",
                        "SCRAPE_FIXTURE": str(tmp_path),
                        "SCRAPE_FAILURE": failure,
                    },
                    "vars": {
                        "services_controller_host": "manager",
                        "local_ip": "192.0.2.48",
                        "docker_services_prometheus_catalog": {
                            "prometheus": {"templates": [{"src": "configs/prometheus/prometheus.yml.j2", "dest": str(config_file)}]}
                        },
                        "docker_services_haproxy_catalog": {
                            "haproxy": {"targets": {"mgt": {"ports": {"metrics": {"published": 18405, "target": 8405}}}}}
                        },
                    },
                    "tasks": [
                        {
                            "name": "Run the actual adapter task file",
                            "ansible.builtin.import_tasks": str(
                                ROOT / "ansible/roles/docker_services/tasks/sub_tasks/prometheus_haproxy_scrape.yml"
                            ),
                        }
                    ],
                    "handlers": yaml.safe_load((ROOT / "ansible/roles/docker_services/handlers/main.yml").read_text()),
                }
            ],
            sort_keys=False,
        )
    )
    cfg = tmp_path / "ansible.cfg"
    cfg.write_text(
        f"[defaults]\ninventory={inventory}\nlocal_tmp={tmp_path / 'ansible-tmp'}\n"
        "vars_plugins_enabled=\n[inventory]\nenable_plugins=yaml\n"
    )
    argv = [str(Path(sys.executable).parent / "ansible-playbook"), str(playbook)] + (["--check"] if failure == "check" else [])
    environment = {**os.environ, "ANSIBLE_CONFIG": str(cfg)}
    environment.pop("ANSIBLE_LOG_PATH", None)
    result = subprocess.run(argv, env=environment, cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert result.returncode == (0 if failure in {"", "check"} else 2), result.stdout + result.stderr
    commands = [json.loads(line) for line in receipt.read_text().splitlines()]
    assert all(command[0] in {"ps", "inspect", "exec", "kill", "query"} for command in commands)
    assert not list(config_dir.glob(".skynet-haproxy-scrape-*"))
    if failure and failure != "reload":
        assert config_file.read_text() == original
        assert not any(command[0] == "kill" for command in commands)
        assert not list(config_dir.glob("prometheus.yml.*"))
    else:
        updated = config_file.read_text()
        before, after = yaml.safe_load(original), yaml.safe_load(updated)
        assert before["global"] == after["global"]
        assert before["scrape_configs"][0] == after["scrape_configs"][0]
        assert before["scrape_configs"][2] == after["scrape_configs"][2]
        assert updated.split('  - job_name: "after"', 1)[1] == original.split('  - job_name: "after"', 1)[1]
        assert updated.split("  - job_name: haproxy", 1)[0] == original.split('  - job_name: "haproxy"', 1)[0]
        old_job, job = before["scrape_configs"][1], after["scrape_configs"][1]
        assert old_job | {"static_configs": job["static_configs"]} == job
        assert job["static_configs"] == old_job["static_configs"] + [{"targets": ["192.0.2.48:18405"]}]
        assert config_file.stat().st_mode & 0o777 == 0o640
        assert len(list(config_dir.glob("prometheus.yml.*"))) == 1
        assert sum(command[0] == "kill" for command in commands) == 1
        # The first write renders a normal unquoted YAML job name. Repeat the
        # real task file to prove that matching and rendering remain idempotent.
        if failure == "reload":
            playbook.write_text(playbook.read_text().replace("SCRAPE_FAILURE: reload", "SCRAPE_FAILURE: ''"))
        repeated = subprocess.run(argv, env=environment, cwd=tmp_path, capture_output=True, text=True, timeout=60)
        assert repeated.returncode == 0, repeated.stdout + repeated.stderr
        assert config_file.read_text() == updated
        commands = [json.loads(line) for line in receipt.read_text().splitlines()]
        assert sum(command[0] == "kill" for command in commands) == (2 if failure == "reload" else 1)
