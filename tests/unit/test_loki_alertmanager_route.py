"""Exercise the actual named Loki route operation with isolated command fixtures."""

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
ORIGINAL = """auth_enabled: false
common:
  path_prefix: /loki
ruler:
  alertmanager_url: http://alertmanager:9093
  enable_api: true
  external_labels: {retained: label}
limits_config:
  retention_period: 168h
"""


def canonical():
    env = Environment(loader=FileSystemLoader(ROOT / "ansible/roles/service_common/templates"), undefined=StrictUndefined)
    return env.get_template("configs/loki-config.yaml.j2").render(
        services_internal_zone="internal.example", services_private_https_port=8443
    )


@pytest.mark.parametrize("case", ["normal", "foreign", "duplicate", "alias"])
def test_only_ruler_url_changes(case):
    text = ORIGINAL
    if case == "foreign":
        text = text.replace("http://alertmanager:9093", "http://unrecognized:9093")
    if case == "duplicate":
        text += "\nruler: {}\n"
    if case == "alias":
        text = text.replace("http://alertmanager:9093", "&shared http://alertmanager:9093") + "unrelated: *shared\n"
    if case != "normal":
        with pytest.raises(Exception, match="source withheld"):
            FILTER.docker_services_loki_alertmanager_route(text, canonical())
        return
    result = FILTER.docker_services_loki_alertmanager_route(text, canonical())
    assert result == text.replace("http://alertmanager:9093", "https://alertmanager.internal.example:8443")
    assert FILTER.docker_services_loki_alertmanager_route(result, canonical()) == result


@pytest.mark.parametrize("failure", ["", "check", "validate", "replacement", "update-before", "update-after", "readiness", "dependency"])
def test_actual_ansible_named_rollout_and_scoped_rollback(tmp_path, failure):
    config = tmp_path / "loki"
    config.mkdir()
    data = config / "data"
    data.mkdir()
    file = config / "loki-config.yaml"
    file.write_text(ORIGINAL)
    file.chmod(0o640)
    (tmp_path / "loaded.yml").write_text(ORIGINAL)
    (tmp_path / "force").write_text("0")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    program = r"""import json,os,sys
from pathlib import Path
import yaml
root=Path(os.environ['ROUTE_FIXTURE']); failure=os.environ['ROUTE_FAILURE']; args=sys.argv[1:]; name=Path(sys.argv[0]).name
with (root/'commands.jsonl').open('a') as s:s.write(json.dumps([name,*args])+'\n')
rows=[json.loads(r) for r in (root/'commands.jsonl').read_text().splitlines()]
force=int((root/'force').read_text()); identity=('a' if force==0 else 'b' if force==1 else 'c')*64
service={'id':'s'*25,'name':'loki_loki','image':'grafana/loki:fixture@sha256:'+'d'*64,
 'mode':{'Replicated':{'Replicas':1}},'update':{'Order':'stop-first','Parallelism':1},
 'mounts':[{'Type':'bind','Source':str(root/'loki'),'Target':'/etc/loki','ReadOnly':True},
           {'Type':'bind','Source':str(root/'loki/data'),'Target':'/loki','ReadOnly':False}],
 'configs':[{'ConfigID':'retained','ConfigName':'unchanged'}],'networks':[{'Target':'retained'}],
 'placement':{'Constraints':['unchanged']},'ports':[{'PublishedPort':3100,'TargetPort':3100}],'force':force}
if name=='docker':
 assert args[:2]==['--host','unix:///var/run/docker.sock'];args=args[2:]
 if args[:2]==['service','inspect']:print(json.dumps(service))
 elif args[:2]==['service','ps']:
  print(json.dumps({'node':'fixture','desired':'Running','state':'Running 1 second ago'}))
 elif args[0]=='ps':
  count=sum(r[0]=='docker' and r[3]=='ps' for r in rows)
  print('e'*64 if failure=='replacement' and count>1 else identity)
 elif args[:2]==['container','inspect']:
  assert args[-1]==identity
  assert '.Config.Env' not in args[3]
  print(json.dumps({'id':identity,'pid':321+force,'running':True,'image_id':'sha256:'+'d'*64,
   'binary':'/usr/bin/loki','managed':True,'service':'loki_loki',
   'mounts':[{'Type':'bind','Source':str(root/'loki'),'Destination':'/etc/loki','RW':False},
             {'Type':'bind','Source':str(root/'loki/data'),'Destination':'/loki','RW':True}]}))
 elif args[:4]==['exec',identity,'/usr/bin/loki','-verify-config']:
  candidate=root/'loki'/args[-1].rsplit('/',1)[1]
  assert yaml.safe_load(candidate.read_text())['ruler']['alertmanager_url']=='https://alertmanager.internal.example:8443'
  if failure=='validate':sys.exit(40)
 elif args==['service','update','--force','--detach=true','s'*25]:
  count=sum(r[0]=='docker' and r[3:5]==['service','update'] for r in rows)
  if failure=='update-before' and count==1:sys.exit(41)
  (root/'force').write_text(str(force+1));(root/'loaded.yml').write_text((root/'loki/loki-config.yaml').read_text())
  if failure=='update-after' and count==1:sys.exit(42)
 else:raise SystemExit('unapproved Docker operation')
elif name=='python3':
 assert args[0]=='-c';compile(args[1],'<identity-query>','exec')
 print(json.dumps({'birth':'fixture-'+args[-1],'netns':'net:['+args[-1]+']'}))
elif name=='nsenter':
 assert args[:1]==['--target'] and args[2]=='--net' and Path(args[3]).parent==Path(sys.executable).parent and args[4]=='-c'
 import io,urllib.request,urllib.error,builtins
 class Response(io.BytesIO):
  status=200
 class Api:
  def open(self,url,timeout):
   assert url in ['http://127.0.0.1:3100/ready','http://127.0.0.1:3100/config'] and timeout==5
   if url.endswith('/ready'):
    if failure=='readiness':raise urllib.error.HTTPError(url,503,'FAKE_SECRET_ERROR',{},None)
    return Response(b'ready')
   return Response((root/'loaded.yml').read_bytes())
 urllib.request.build_opener=lambda *args:Api()
 if failure=='dependency':
  original_import=builtins.__import__
  def missing_yaml(name,*args,**kwargs):
   if name=='yaml':raise ModuleNotFoundError('FAKE_SECRET_IMPORT_ERROR')
   return original_import(name,*args,**kwargs)
  builtins.__import__=missing_yaml
 sys.argv=['actual-query',*args[6:]]
 exec(compile(args[5],'<actual-loaded-route-query>','exec'),{'__name__':'__main__'})
else:raise SystemExit('unapproved operation')
"""
    for name in ["docker", "python3", "nsenter"]:
        executable = bindir / name
        executable.write_text("#!" + sys.executable + "\n" + program)
        executable.chmod(0o755)
    roles = tmp_path / "roles"
    (roles / "service_common").mkdir(parents=True)
    (roles / "service_common/templates").symlink_to(ROOT / "ansible/roles/service_common/templates", target_is_directory=True)
    inventory = tmp_path / "inventory.yml"
    inventory.write_text(
        yaml.safe_dump({"all": {"hosts": {"fixture": {"ansible_connection": "local", "ansible_python_interpreter": sys.executable}}}})
    )
    playbook = tmp_path / "playbook.yml"
    playbook.write_text(
        yaml.safe_dump(
            [
                {
                    "name": "Actual named rollout without daemons",
                    "hosts": "fixture",
                    "gather_facts": False,
                    "environment": {"PATH": str(bindir) + ":/usr/bin:/bin", "ROUTE_FIXTURE": str(tmp_path), "ROUTE_FAILURE": failure},
                    "vars": {
                        "services_internal_zone": "internal.example",
                        "services_private_https_port": 8443,
                        "services_controller_host": "fixture",
                        "docker_services_loki_catalog": {
                            "loki": {
                                "templates": [{"src": "configs/loki-config.yaml.j2", "dest": str(file)}],
                                "volumes": {"data": {"source": str(data)}},
                            }
                        },
                    },
                    "tasks": [
                        {
                            "name": "Run actual scoped role operation",
                            "ansible.builtin.import_tasks": str(ROLE / "tasks/sub_tasks/loki_alertmanager_route.yml"),
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
    assert "FAKE_SECRET" not in result.stdout + result.stderr
    if failure == "readiness":
        assert "readiness: HTTP 503" in result.stdout
        assert "loaded_destination=http://alertmanager:9093" in result.stdout
    if failure == "dependency":
        assert "PyYAML unavailable in selected query interpreter" in result.stdout
    rows = [json.loads(row) for row in (tmp_path / "commands.jsonl").read_text().splitlines()]
    updates = [r for r in rows if r[0] == "docker" and r[3:5] == ["service", "update"]]
    assert not list(config.glob(".skynet-ruler-route-*"))
    assert file.stat().st_mode & 0o777 == 0o640
    if failure:
        assert file.read_text() == ORIGINAL
    else:
        assert file.read_text() == ORIGINAL.replace("http://alertmanager:9093", "https://alertmanager.internal.example:8443")
        assert len(updates) == 1
        repeat = subprocess.run(args, env=env, cwd=tmp_path, capture_output=True, text=True, timeout=90)
        assert repeat.returncode == 0, repeat.stdout + repeat.stderr
        later = [json.loads(row) for row in (tmp_path / "commands.jsonl").read_text().splitlines()]
        assert sum(r[0] == "docker" and r[3:5] == ["service", "update"] for r in later) == 1
    if failure in {"update-before", "update-after"}:
        assert len(updates) == (1 if failure == "update-before" else 2) and (tmp_path / "loaded.yml").read_text() == ORIGINAL
    elif failure:
        assert not updates


@pytest.mark.parametrize("case", ["success", "readiness", "config-http", "malformed", "oversized", "sensitive-destination"])
def test_actual_embedded_query_retains_partial_observations_without_source_leaks(case):
    tasks = yaml.safe_load((ROLE / "tasks/sub_tasks/loki_alertmanager_route.yml").read_text())
    query = next(t for t in tasks if t["name"].endswith("Check original readiness and loaded URL"))["ansible.builtin.command"]["argv"][6]
    setup = r"""import io,sys,urllib.request,urllib.error
case=sys.argv[1]
class Response(io.BytesIO):
    status=200
class Api:
    def open(self,url,timeout):
        assert timeout==5 and url in ['http://127.0.0.1:3100/ready','http://127.0.0.1:3100/config']
        if url.endswith('/ready'):
            if case=='readiness':raise urllib.error.HTTPError(url,503,'FAKE_SECRET_HTTP_BODY',{},None)
            return Response(b'ready')
        if case=='config-http':raise urllib.error.HTTPError(url,403,'FAKE_SECRET_HTTP_BODY',{},None)
        if case=='malformed':return Response(b'ruler: [FAKE_SECRET_YAML')
        if case=='oversized':return Response(b'x'*4194305)
        value='http://user:FAKE_SECRET_URL@unexpected:9093/message?token=FAKE_SECRET_TOKEN' if case=='sensitive-destination' else 'http://alertmanager:9093'
        return Response(('unrelated: FAKE_SECRET_CONFIG\nruler:\n  alertmanager_url: '+value+'\n').encode())
urllib.request.build_opener=lambda *args:Api()
sys.argv=['query','http://alertmanager:9093','https://alertmanager.internal.example:8443']
"""
    result = subprocess.run([sys.executable, "-c", setup + query, case], capture_output=True, text=True, timeout=10)
    assert result.returncode == (0 if case == "success" else 1)
    assert result.stderr == ""
    assert "FAKE_SECRET" not in result.stdout
    report = json.loads(result.stdout)
    assert report["ready"] is (case != "readiness")
    assert report["url"] == ("http://alertmanager:9093" if case in {"success", "readiness"} else None)
    if case == "readiness":
        assert report["failures"] == ["readiness: HTTP 503"]
    if case == "config-http":
        assert report["failures"] == ["configuration: HTTP 403"]
