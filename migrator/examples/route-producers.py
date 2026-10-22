"""Embedded route-observation producers, executed only by an authorized caller.

These strings preserve tested sanitized API projection and account-owned handshake
behavior. They do not collect evidence or contact services when imported. A
handshake is not authenticated SQL or notification delivery acceptance.
"""

native = r"""
import importlib.util,json,sys
spec=importlib.util.spec_from_file_location('u','/opt/homelab/ansible/operator/utility-preparation.py')
u=importlib.util.module_from_spec(spec);spec.loader.exec_module(u)
try:
    print(json.dumps(u.qualified_database_handshake(int(sys.argv[1]),sys.argv[2],sys.argv[3],int(sys.argv[4]))))
except Exception as error:
    print('qualified PostgreSQL child failed: '+type(error).__name__,file=sys.stderr);sys.exit(1)
"""

api = r"""
import json,sys,urllib.request,urllib.parse,yaml
name,port=sys.argv[1],int(sys.argv[2])
def get(path,as_yaml=False):
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open('http://127.0.0.1:'+str(port)+path,timeout=5) as response:
        body=response.read(4194305)
    if len(body)>4194304:raise ValueError('response exceeds bound')
    return yaml.safe_load(body) if as_yaml else json.loads(body)
def route(value):
    import importlib.util
    spec=importlib.util.spec_from_file_location('u','/opt/homelab/ansible/operator/utility-preparation.py')
    u=importlib.util.module_from_spec(spec);spec.loader.exec_module(u)
    return u.destination_metadata(value)
try:
    if name=='prometheus':
        managers=get('/api/v1/alertmanagers');targets=get('/api/v1/targets?state=active')
        assert managers['status']==targets['status']=='success'
        rows=[route(r['url']) for r in managers['data']['activeAlertmanagers']]
        scrapes=[{**route(r['scrapeUrl']),'health':r['health']} for r in targets['data']['activeTargets'] if r['scrapePool']=='alertmanager']
        result={'delivery':rows,'scrapes':scrapes}
    elif name=='loki':
        cfg=get('/config',as_yaml=True)
        value=cfg.get('ruler',{}).get('alertmanager_url')
        result={'delivery':[] if not value else [route(v.strip()) for v in value.split(',')]}
    elif name=='alertmanager':
        cfg=yaml.safe_load(get('/api/v2/status')['config']['original'])
        result={'delivery':[route(w['url']) for r in cfg.get('receivers',[]) for w in r.get('webhook_configs',[])]}
    else:raise ValueError('unexpected service')
    print(json.dumps(result))
except Exception as error:
    print(name+' local API projection failed: '+type(error).__name__+'; no configuration or URL source emitted',file=sys.stderr);sys.exit(1)
"""
