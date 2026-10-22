"""Clearly labeled, persistent demo workspace. NEVER called by addon installation."""
import json
import os
from pathlib import Path
import sys
import time
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
from core import Store
DATA = Path(sys.argv[1]).resolve()
DATA.mkdir(parents=True, exist_ok=True)
cfg = {'id': 'robo-storage-aegis', 'version': '1.2.0', 'bind': '0.0.0.0', 'port': 8080, 'host': 'burrow', 'demo': True, 'mesh': str(DATA / 'mesh')}
config = DATA / 'config.json'
config.write_text(json.dumps(cfg))
os.chmod(config, 0o600)
store = Store(DATA)
if not store.state['groups']:
    now = int(time.time())
    store.state['groups'] = [
        {'id': 'a000000000000001', 'name': 'Creative studio', 'sub': 'studio', 'domain': 'example.com', 'tunnelSub': '', 'url': '', 'routeState': 'demo', 'created': now},
        {'id': 'a000000000000002', 'name': 'Personal cloud', 'sub': 'cloud', 'domain': 'example.com', 'tunnelSub': '', 'url': '', 'routeState': 'demo', 'created': now}]
    def server(id,gid,name,kind,used,limit,types,path='',partitions=None):
        return {'id': id, 'group': gid, 'name': name, 'kind': kind, 'limit': limit, 'used': used, 'capacity': limit, 'verified': True, 'status': 'online', 'url': '', 'partitions': partitions or [], 'inventory': [], 'types': types, 'lastTest': now-300, 'error': '', 'path': path, 'readOnly': False, 'lastSeen': now}
    a,b=[g['id'] for g in store.state['groups']]
    store.state['servers']=[
      server('b000000000000001',a,'Studio archive','e2',347_200_000_000,1_000_000_000_000,{'video':162_000_000_000,'images':115_000_000_000,'audio':43_000_000_000,'code':12_000_000_000,'text':15_200_000_000}),
      server('b000000000000002',a,'Render workstation','linux',142_800_000_000,500_000_000_000,{'video':100_000_000_000,'images':22_800_000_000,'code':20_000_000_000},'~/studio-storage',[{'id':'c000000000000001','name':'Project files','path':'projects','limit':200_000_000_000}]),
      server('b000000000000003',a,'Shared resources','cloudgate',28_400_000_000,100_000_000_000,{'text':12_000_000_000,'images':10_000_000_000,'other':6_400_000_000}),
      server('b000000000000004',b,'Home storage','linux',86_500_000_000,250_000_000_000,{'images':45_000_000_000,'video':25_000_000_000,'audio':12_000_000_000,'text':4_500_000_000},'~/personal-cloud'),
      server('b000000000000005',b,'Cloud backup','e2',124_100_000_000,500_000_000_000,{'images':61_000_000_000,'video':42_000_000_000,'other':21_100_000_000})]
    store.state['users']=[
      {'id':'d000000000000001','group':a,'username':'alex','enabled':True,'passwordHash':'DEMO-NOT-A-REAL-LOGIN','rules':[{'path':'','access':'write'},{'path':'finance','access':'none'}]},
      {'id':'d000000000000002','group':a,'username':'studio-team','enabled':True,'passwordHash':'DEMO-NOT-A-REAL-LOGIN','rules':[{'path':'shared','access':'write'},{'path':'archive','access':'read'}]},
      {'id':'d000000000000003','group':b,'username':'alex','enabled':True,'passwordHash':'DEMO-NOT-A-REAL-LOGIN','rules':[{'path':'','access':'write'}]}]
    store.state['audit']=[{'at':now-300,'action':'Example inventory','detail':'Illustrative sample usage, not a real provider scan.'},{'at':now-2400,'action':'Example group','detail':'Creative studio — IDrive E2, Linux and CloudGate'},{'at':now-3600,'action':'Example access rules','detail':'Directory rules shown for the studio team'}]
    store.save()
os.execv(sys.executable, [sys.executable, str(ROOT / 'app' / 'server.py'), str(config)])
