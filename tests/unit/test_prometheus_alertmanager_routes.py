"""Run the existing-Docker route transition offline, including scoped rollback."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parents[2]
ROLE = ROOT / "ansible/roles/docker_services"
SPEC = importlib.util.spec_from_file_location("route_filter", ROLE / "filter_plugins/docker_services_alertmanager_routes.py")
FILTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FILTER)
ORIGINAL = """# preserve this comment
global:
  scrape_interval: 15s
alerting:
  alert_relabel_configs:
    - source_labels: [retained]
      target_label: application
  alertmanagers:
    - api_version: v2
      static_configs:
        - targets: ["alertmanager:9093"]
          labels:
            retained: label
rule_files: [/etc/prometheus/rules/*.yml]
scrape_configs:
  - job_name: "haproxy"
    static_configs:
      - targets: ["haproxy:8405", "192.0.2.48:18405"]

  - job_name: "alertmanager"
    scrape_interval: 30s
    static_configs:
      - targets: ["alertmanager:9093"]
        labels:
          retained: label

  - job_name: "unrelated"
    static_configs:
      - targets: ["untouched:1111"]
    basic_auth:
      password: FAKE_SECRET_ONLY
"""


def fragments():
    env = Environment(loader=FileSystemLoader(ROOT / "ansible/roles/service_common/templates"), undefined=StrictUndefined)
    args = {"services_internal_zone": "internal.example", "services_private_https_port": 8443}
    return (
        yaml.safe_load(env.get_template("configs/prometheus/alertmanager-discovery.yml.j2").render(args)),
        yaml.safe_load(env.get_template("configs/prometheus/alertmanager-scrape.yml.j2").render(args))[0],
    )


@pytest.mark.parametrize("case", ["normal", "ambiguous", "custom", "duplicate", "alias"])
def test_patch_preserves_every_other_setting_and_is_idempotent(case):
    discovery, job = fragments()
    text = ORIGINAL
    if case == "ambiguous":
        text += '\n  - job_name: "alertmanager"\n    static_configs: []\n'
    if case == "custom":
        text = text.replace('targets: ["alertmanager:9093"]', 'targets: ["another:9093"]', 1)
    if case == "duplicate":
        text = text.replace("global:\n", "global: {}\nglobal:\n")
    if case == "alias":
        text = text.replace('targets: ["alertmanager:9093"]', 'targets: &shared ["alertmanager:9093"]', 1).replace(
            'targets: ["untouched:1111"]', "targets: *shared"
        )
    if case != "normal":
        with pytest.raises(Exception, match="source withheld"):
            FILTER.docker_services_prometheus_alertmanager_routes(text, discovery, job)
        return
    before = yaml.safe_load(text)
    result = FILTER.docker_services_prometheus_alertmanager_routes(text, discovery, job)
    after = yaml.safe_load(result)
    assert after["global"] == before["global"] and after["rule_files"] == before["rule_files"]
    assert after["alerting"]["alert_relabel_configs"] == before["alerting"]["alert_relabel_configs"]
    assert after["scrape_configs"][0] == before["scrape_configs"][0]
    assert after["scrape_configs"][2] == before["scrape_configs"][2]
    assert result.startswith("# preserve this comment\n")
    assert result.split('  - job_name: "unrelated"', 1)[1] == text.split('  - job_name: "unrelated"', 1)[1]
    assert after["alerting"]["alertmanagers"][0]["static_configs"][0]["labels"] == {"retained": "label"}
    assert after["scrape_configs"][1]["static_configs"][0]["labels"] == {"retained": "label"}
    assert FILTER.docker_services_prometheus_alertmanager_routes(result, discovery, job) == result


@pytest.mark.parametrize("case", ["absent", "alias", "existing", "custom", "duplicate", "invalid", "relabel", "anchor"])
def test_scraparr_job_preserves_other_configuration_and_rejects_ambiguous_scope(case):
    job = {"job_name": "scraparr", "scrape_interval": "30s", "scrape_timeout": "10s", "static_configs": [{"targets": ["192.0.2.48:17100"]}]}
    text = ORIGINAL
    if case != "absent":
        target = "192.0.2.48:17100" if case == "existing" else "scraparr:7100"
        if case == "custom":
            target = "another:7100"
        block = f'  - job_name: "scraparr"\n    scrape_interval: 20s\n    static_configs:\n      - targets: ["{target}"]\n'
        if case == "relabel":
            block += "    relabel_configs: [{target_label: instance, replacement: wrong}]\n"
        if case == "anchor":
            block = block.replace('targets: ["scraparr:7100"]', 'targets: &shared ["scraparr:7100"]')
            text = text.replace('["untouched:1111"]', "*shared")
        text = text.replace("scrape_configs:\n", "scrape_configs:\n" + block * (2 if case == "duplicate" else 1))
        if case == "invalid":
            job["static_configs"][0]["targets"] = ["999.0.2.48:17100"]
    if case in {"custom", "duplicate", "invalid", "relabel", "anchor"}:
        with pytest.raises(Exception, match="source withheld"):
            FILTER.docker_services_prometheus_scraparr_job(text, job)
        return
    result = FILTER.docker_services_prometheus_scraparr_job(text, job)
    before, after = yaml.safe_load(text), yaml.safe_load(result)
    assert {k: v for k, v in after.items() if k != "scrape_configs"} == {k: v for k, v in before.items() if k != "scrape_configs"}
    assert [j for j in after["scrape_configs"] if j["job_name"] != "scraparr"] == [
        j for j in before["scrape_configs"] if j["job_name"] != "scraparr"
    ]
    assert result.split('  - job_name: "unrelated"', 1)[1] == text.split('  - job_name: "unrelated"', 1)[1]
    selected = next(j for j in after["scrape_configs"] if j["job_name"] == "scraparr")
    assert selected["static_configs"] == [{"targets": ["192.0.2.48:17100"]}]
    assert selected["scrape_interval"] == ("30s" if case == "absent" else "20s")
    assert FILTER.docker_services_prometheus_scraparr_job(result, job) == result


@pytest.mark.parametrize("kind", ["alertmanager", "scraparr"])
@pytest.mark.parametrize("failure", ["", "check", "promtool", "replacement", "namespace", "reload"])
def test_actual_ansible_route_operation(tmp_path, failure, kind):
    config = tmp_path / "prometheus"
    config.mkdir()
    file = config / "prometheus.yml"
    file.write_text(ORIGINAL)
    file.chmod(0o640)
    (tmp_path / "loaded.yml").write_text(ORIGINAL)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    program = r"""import json,os,sys
from pathlib import Path
import yaml
root=Path(os.environ['ROUTE_FIXTURE']);failure=os.environ['ROUTE_FAILURE'];kind=os.environ['ROUTE_KIND']
args=sys.argv[1:];name=Path(sys.argv[0]).name
with (root/'commands.jsonl').open('a') as stream:stream.write(json.dumps([name,*args])+'\n')
records=[json.loads(row) for row in (root/'commands.jsonl').read_text().splitlines()]
identity='a'*64
if name=='docker':
 assert args[:2]==['--host','unix:///var/run/docker.sock'];args=args[2:]
 if args[0]=='ps':
  assert 'label=com.docker.swarm.service.name=prometheus_prometheus' in args
  count=sum(row[0]=='docker' and row[3]=='ps' for row in records)
  print('b'*64 if failure=='replacement' and count>1 else identity)
 elif args[:2]==['container','inspect']:print('321')
 elif args[0]=='inspect':
  assert '.Config.Env' not in args[2]
  print(json.dumps({'id':identity,'pid':321,'running':True,'managed_config':True,'service':'prometheus_prometheus',
                   'mounts':[{'Type':'bind','Source':str(root/'prometheus'),'Destination':'/etc/prometheus','RW':False}]}))
 elif args[:5]==['exec',identity,'/bin/promtool','check','config']:
  candidate=root/'prometheus'/Path(args[-1]).name
  cfg=yaml.safe_load(candidate.read_text())
  if kind=='alertmanager':assert cfg['alerting']['alertmanagers'][0]['scheme']=='https'
  else:
   job=next(j for j in cfg['scrape_configs'] if j['job_name']=='scraparr');assert job['static_configs']==[{'targets':['192.0.2.48:17100']}]
  if failure=='promtool':sys.exit(41)
 elif args==['kill','--signal','HUP',identity]:
  count=sum(row[0]=='docker' and row[3]=='kill' for row in records)
  if failure=='reload' and count==1:sys.exit(42)
  (root/'loaded.yml').write_text((root/'prometheus/prometheus.yml').read_text())
 else:raise SystemExit('unapproved Docker operation')
elif name=='python3':
 assert args[0]=='-c' and args[-1]=='321';compile(args[1],'<actual-identity-query>','exec')
 count=sum(row[0]=='python3' for row in records)
 print(json.dumps({'pid':321,'birth':'fixture','netns':'changed' if failure=='namespace' and count>1 else 'net:[fixture]'}))
elif name=='nsenter':
 assert args[:5]==['--target','321','--net','/usr/bin/python3','-c']
 compile(args[5],'<actual-api-query>','exec')
 if 'status/config' in args[5]:print((root/'loaded.yml').read_text())
 elif kind=='scraparr':
  cfg=yaml.safe_load((root/'loaded.yml').read_text());target=next(j for j in cfg['scrape_configs'] if j['job_name']=='scraparr')['static_configs'][0]['targets'][0]
  print(json.dumps([{'url':'http://'+target+'/metrics','health':'up','labels':{'job':'scraparr','instance':target}}]))
 else:
  cfg=yaml.safe_load((root/'loaded.yml').read_text());target=cfg['alerting']['alertmanagers'][0]['static_configs'][0]['targets'][0]
  print(json.dumps({'delivery':['https://'+target+'/api/v2/alerts'],'scrapes':[{'url':'https://'+target+'/metrics','health':'up'}]}))
else:raise SystemExit('unapproved runtime operation')
"""
    for name in ["docker", "nsenter", "python3"]:
        executable = bindir / name
        executable.write_text("#!" + sys.executable + "\n" + program)
        executable.chmod(0o755)
    roles = tmp_path / "roles"
    (roles / "service_common").mkdir(parents=True)
    (roles / "service_common/templates").symlink_to(ROOT / "ansible/roles/service_common/templates", target_is_directory=True)
    inventory = tmp_path / "inventory.yml"
    inventory.write_text(
        yaml.safe_dump(
            {
                "all": {
                    "hosts": {
                        "fixture": {"ansible_connection": "local", "ansible_python_interpreter": sys.executable, "local_ip": "192.0.2.48"}
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
                    "name": "Real-task route regression without daemons",
                    "hosts": "fixture",
                    "gather_facts": False,
                    "environment": {
                        "PATH": str(bindir) + ":/usr/bin:/bin",
                        "ROUTE_FIXTURE": str(tmp_path),
                        "ROUTE_FAILURE": failure,
                        "ROUTE_KIND": kind,
                    },
                    "vars": {
                        "docker_services_prometheus_routes_kind": kind,
                        "services_controller_host": "fixture",
                        "services_internal_zone": "internal.example",
                        "services_private_https_port": 8443,
                        "docker_services_prometheus_catalog": {
                            "prometheus": {"templates": [{"src": "configs/prometheus/prometheus.yml.j2", "dest": str(file)}]}
                        },
                    },
                    "tasks": [
                        {
                            "name": "Run the actual scoped adapter operation",
                            "ansible.builtin.import_tasks": str(ROLE / "tasks/sub_tasks/prometheus_alertmanager_routes.yml"),
                        }
                    ],
                }
            ],
            sort_keys=False,
        )
    )
    cfg = tmp_path / "ansible.cfg"
    cfg.write_text(
        f"[defaults]\ninventory={inventory}\nlocal_tmp={tmp_path / 'ansible-tmp'}\nfilter_plugins={ROLE / 'filter_plugins'}\nvars_plugins_enabled=\n[inventory]\nenable_plugins=yaml\n"
    )
    env = {**os.environ, "ANSIBLE_CONFIG": str(cfg)}
    env.pop("ANSIBLE_LOG_PATH", None)
    args = [str(Path(sys.executable).parent / "ansible-playbook"), str(playbook)] + (["--check"] if failure == "check" else [])
    result = subprocess.run(args, env=env, cwd=tmp_path, capture_output=True, text=True, timeout=90)
    assert result.returncode == (0 if failure in {"", "check"} else 2), result.stdout + result.stderr
    assert "FAKE_SECRET_ONLY" not in result.stdout + result.stderr
    commands = [json.loads(line) for line in (tmp_path / "commands.jsonl").read_text().splitlines()]
    assert not list(config.glob(".skynet-alertmanager-routes-*"))
    if failure:
        assert file.read_text() == ORIGINAL
    else:
        changed = yaml.safe_load(file.read_text())
        if kind == "scraparr":
            assert changed["scrape_configs"][1:] == yaml.safe_load(ORIGINAL)["scrape_configs"]
            assert changed["alerting"] == yaml.safe_load(ORIGINAL)["alerting"]
        else:
            assert changed["scrape_configs"][0] == yaml.safe_load(ORIGINAL)["scrape_configs"][0]
        repeated = subprocess.run(args, env=env, cwd=tmp_path, capture_output=True, text=True, timeout=90)
        assert repeated.returncode == 0, repeated.stdout + repeated.stderr
        later = [json.loads(line) for line in (tmp_path / "commands.jsonl").read_text().splitlines()]
        assert sum(row[0] == "docker" and row[3] == "kill" for row in later) == 1
    if failure == "reload":
        assert sum(row[0] == "docker" and row[3] == "kill" for row in commands) == 2
    elif failure:
        assert not any(row[0] == "docker" and row[3] == "kill" for row in commands)
    assert file.stat().st_mode & 0o777 == 0o640
