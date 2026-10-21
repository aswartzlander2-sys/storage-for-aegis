"""Exercise real scripts with weft-run, then linked-copy and port-ownership checks.
Usage: python tests/lifecycle_acceptance.py /path/to/weft-checkout
"""
import http.server
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
WEFT=Path(sys.argv[1]).resolve()
env={**os.environ,'WEFT_NO_SYSTEMD':'1'}
PORT=18898
DATA=WEFT/'.weft-dev/robo-storage-aegis/data'

def run(verb,*args,expected=0):
 cmd=['node',str(WEFT/'tools/weft-run.mjs'),str(ROOT),verb,'--host','burrow',*args]
 r=subprocess.run(cmd,cwd=WEFT,env=env,text=True,capture_output=True,timeout=40)
 print(r.stdout,end='');print(r.stderr,end='');assert r.returncode==expected,(verb,r.returncode)
 return r.stdout

def health():
 with urllib.request.urlopen('http://127.0.0.1:%d/health'%PORT,timeout=2) as r:return json.load(r)

run('install','--set','PORT='+str(PORT))
try:
 first=int((DATA/'robo-storage-aegis.pid').read_text())
 (DATA/'retention-test.txt').write_text('keep me')
 run('install')
 second=int((DATA/'robo-storage-aegis.pid').read_text());assert second!=first
 assert '"state":"running"' in run('status')
 print('Idempotent second install: one current service, running')
 before={str(p.relative_to(DATA)):(p.stat().st_size,p.stat().st_mtime_ns) for p in DATA.rglob('*') if p.is_file()}
 run('detect');after={str(p.relative_to(DATA)):(p.stat().st_size,p.stat().st_mtime_ns) for p in DATA.rglob('*') if p.is_file()}
 assert before==after;print('Detect: read-only filesystem check passed')
 run('update');assert '"state":"running"' in run('status');assert (DATA/'retention-test.txt').read_text()=='keep me'
 print('Update: data-retention sentinel preserved')
 linked=WEFT/'.weft-dev/robo-storage-aegis-linked/data';linked.mkdir(parents=True,exist_ok=True)
 manifest=json.loads((ROOT/'forge-addon.json').read_text())
 e={**env,'ADDON_ID':manifest['id'],'ADDON_DIR':str(ROOT),'ADDON_DATA':str(linked),'ADDON_VERSION':manifest['version'],'ADDON_HOST':'burrow','ADDON_BIND':'127.0.0.1','ADDON_SETTING_PORT':str(PORT),'ADDON_ADOPT':'1','ADDON_UPDATE':'0'}
 pid=int((DATA/'robo-storage-aegis.pid').read_text())
 for script in ['install','uninstall']:
  r=subprocess.run(['bash',str(ROOT/manifest['scripts'][script])],env=e,cwd=ROOT,text=True,capture_output=True,timeout=15);print(r.stdout,end='');assert r.returncode==0
 assert json.loads((linked/'config.json').read_text())['linked'] is True
 assert int((DATA/'robo-storage-aegis.pid').read_text())==pid and health()['app']==manifest['id']
 print('Adopted link: no second process; linked uninstall left owner running')
finally:run('uninstall')

class Other(http.server.BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def do_GET(self):
  self.send_response(200);self.end_headers();self.wfile.write(b'{"app":"different-application","ok":true}')
server=http.server.ThreadingHTTPServer(('127.0.0.1',PORT),Other)
threading.Thread(target=server.serve_forever,daemon=True).start()
try:
 run('install',expected=1);assert health()['app']=='different-application'
 print('Foreign port: installation refused; other application still answering')
finally:server.shutdown();server.server_close()

# A stale PID must not signal an unrelated process.
sleeper=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])
try:
 (DATA/'robo-storage-aegis.pid').write_text(str(sleeper.pid))
 out=run('uninstall');assert 'Stale service PID was ignored' in out;assert sleeper.poll() is None
 print('Stale PID: unrelated process was not signalled')
finally:sleeper.terminate();sleeper.wait(timeout=5)
print('Lifecycle/linking/idempotence/ownership acceptance: passed')
