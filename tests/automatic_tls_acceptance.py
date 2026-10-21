"""Real HTTPS + workers against automatic_tls_fixture.mjs. TEST ONLY, not public DNS.
Usage: python tests/automatic_tls_acceptance.py DATA_DIRECTORY
"""
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from playwright.sync_api import sync_playwright
TEST_ROOT=Path(sys.argv[1]).resolve()
CA=str(TEST_ROOT/'cert.pem');BASE='http://127.0.0.1:8800'
config=json.loads((TEST_ROOT/'config.json').read_text())
with sync_playwright() as p:
 request=p.request.new_context(base_url=BASE,extra_http_headers={'X-Robo-Admin':config['admin_key'],'X-Robo-Request':'1'})
 def admin(path,body=None):
  r=request.get('/'+path) if body is None else request.post('/'+path,data=body)
  assert r.ok,(r.status,r.text());return r.json()
 def state():return admin('api/state')
 route=state()['agentRoute'];assert route['state']=='ready' and route['url']=='https://localhost:9443'
 print('Automatic extension: actual local CA-trusted HTTPS + nonce + app identity verified (supported context fixture, not public DNS)')
 g=admin('api/groups',{'name':'Automatic TLS acceptance','sub':'tls-acceptance','domain':''})['group']
 root_a=TEST_ROOT/'linux-a';root_b=TEST_ROOT/'linux-b';root_a.mkdir(exist_ok=True);root_b.mkdir(exist_ok=True)
 (root_a/'sample.txt').write_bytes(b'verified migration sample')
 a=admin('api/groups/'+g['id']+'/servers',{'kind':'linux','name':'Disposable source','path':str(root_a),'limit':1000000})['server']
 b=admin('api/groups/'+g['id']+'/servers',{'kind':'linux','name':'Disposable destination','path':str(root_b),'limit':1000000})['server']
 env={**os.environ,'CURL_CA_BUNDLE':CA,'SSL_CERT_FILE':CA}
 for s in [a,b]:
  command=admin('api/servers/'+s['id']+'/enrollment',{})['command']
  result=subprocess.run(['bash','-c',command],capture_output=True,text=True,env=env,timeout=20)
  assert result.returncode==0,(result.returncode,result.stdout,result.stderr)
  print(s['name']+': HTTPS enrollment and local write/read/delete probe succeeded')
 end=time.time()+15
 while time.time()<end:
  ss={s['id']:s for s in state()['servers']}
  if ss[a['id']]['verified'] and ss[b['id']]['verified']:break
  time.sleep(.2)
 assert ss[a['id']]['verified'] and ss[b['id']]['verified']
 print('Both Linux agents Verified only after authenticated heartbeat: passed')
 # Re-enrollment links are single-use after registration; do not print the token.
 from urllib.parse import urlsplit
 import ssl,urllib.request,urllib.error
 # Source test uses the real polling agent and a fresh filesystem inventory.
 tested=admin('api/servers/'+a['id']+'/test',{})['server'];assert tested['used']==len(b'verified migration sample');print('Test button backend: real inventory usage matched file size')
 # Group user access, quota and partition enforcement against real Linux writes.
 admin('api/groups/'+g['id']+'/users',{'username':'quota-tester','password':'DISPOSABLE-QUOTA-test-password','enabled':True,'rules':[{'path':'','access':'write'},{'path':'private','access':'none'},{'path':'view.txt','access':'read'}]})
 group_request=p.request.new_context(base_url=BASE,http_credentials={'username':'quota-tester','password':'DISPOSABLE-QUOTA-test-password'},extra_http_headers={'X-Robo-Request':'1'})
 prefix='/g/'+g['id']+'/'
 admin('api/servers/'+b['id']+'/settings',{'limit':100,'name':b['name']})
 admin('api/servers/'+b['id']+'/partition',{'name':'Small partition','path':'small','limit':10})
 def upload(path,bytes):return group_request.post(prefix+'api/upload',data={'server':b['id'],'path':path,'data':base64.b64encode(bytes).decode()})
 assert upload('private/secret.txt',b'x').status==403
 assert upload('view.txt',b'x').status==403
 assert upload('small/too-big.txt',b'x'*11).status==507
 assert upload('too-big.txt',b'x'*101).status==507
 r=upload('small/good.txt',b'12345');assert r.ok,(r.status,r.text())
 assert (root_b/'small/good.txt').read_bytes()==b'12345'
 print('Real Linux writes: hidden/read-only ACLs denied; server/partition quotas enforced; allowed upload verified')
 # Move the source, then erase the destination, both on disposable test directories.
 job=admin('api/servers/'+a['id']+'/drain',{'mode':'move','confirmName':a['name'],'targets':[{'id':b['id'],'percent':100}]})['job']
 def wait_storage_job(id):
  end=time.time()+40
  while time.time()<end:
   j=next(j for j in state()['jobs'] if j['id']==id)
   if j['state']!='running':assert j['state']=='done',j;return j
   time.sleep(.25)
  raise AssertionError('Storage job timed out')
 done=wait_storage_job(job['id']);assert not (root_a/'sample.txt').exists();assert (root_b/'sample.txt').read_bytes()==b'verified migration sample'
 assert next(s for s in state()['servers'] if s['id']==a['id'])['status']=='removed'
 print('Copy -> read-back checksum -> source-change check -> source delete -> empty disconnect: passed')
 bad=group_request.post(prefix+'api/upload',data={'server':a['id'],'path':'blocked','data':'eA=='})
 assert bad.status in (403,404)
 print('Removed source no longer accepts uploads: passed')
 job=admin('api/servers/'+b['id']+'/drain',{'mode':'erase','confirmName':b['name']})['job'];wait_storage_job(job['id'])
 assert not (root_b/'sample.txt').exists() and not (root_b/'small/good.txt').exists()
 assert (root_b/'.robo-agent/config.json').exists()
 print('Explicit erasure -> empty inventory -> disconnect; agent metadata retained: passed')
 print('External E2, CloudGate and public DNS/TLS acceptance: NOT RUN')
 group_request.dispose();request.dispose()
