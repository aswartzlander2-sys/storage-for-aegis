"""Real HTTP regressions for setup removal; fixtures never contact real providers."""
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import secrets
import socket
import struct
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
from core import Store, digest

class UnverifiedRemovalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.data=Path(cls.tmp.name)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        cls.base='http://127.0.0.1:'+str(port)
        state=Store(cls.data);g=state.group({'name':'Removal regression','sub':'removal'})
        cls.legacy={}
        for kind in ('e2','cloudgate','linux','windows'):
            body=cls.body(kind,'Legacy '+kind);s=state.server(g['id'],body)
            s.update(status='draining',inventory=[{'path':'keep.txt','size':9}],used=9)
            if kind in ('linux','windows'):s.update(probeDone=True,agentToken=digest('old-agent-'+kind+'-'*40))
            state.state['jobs'].append({'id':secrets.token_hex(8),'server':s['id'],'state':'running' if kind=='windows' else 'error','mode':'erase','done':0,'total':0,'detail':'Old unreachable scan'})
            state.state['enrollments'].append({'id':digest('old-installer-'+kind+'-'*40),'server':s['id'],'used':False,'expires':time.time()+900,'baseUrl':'https://checked.example.com'})
            cls.legacy[kind]=s['id']
        cls.unused=state.server(g['id'],cls.body('linux','Old unenrolled worker'));cls.unused.update(status='draining');state.state['jobs'].append({'id':secrets.token_hex(8),'server':cls.unused['id'],'state':'error','mode':'erase','done':0,'total':0,'detail':'Old offline scan'})
        state.state['usedInstallers']=[digest('spent-installer-'+'-'*40)];state.save()
        cls.keep=cls.data/'remote-folder';cls.keep.mkdir();(cls.keep/'keep.txt').write_text('keep data')
        conf={'id':'robo-storage-aegis','version':'1.3.2','port':port,'bind':'127.0.0.1','host':'burrow','mesh':str(cls.data/'mesh'),'admin_key':'TEST-REMOVAL-ADMIN','burrow_socket':str(cls.data/'control.sock')}
        config=cls.data/'config.json';config.write_text(json.dumps(conf))
        bootstrap="import sys,runpy;sys.path.insert(0,"+repr(str(ROOT/'app'))+");import backends;backends.request=lambda *a,**k: (_ for _ in ()).throw(AssertionError('No remote provider requests allowed in removal fixture'));runpy.run_path("+repr(str(ROOT/'app/server.py'))+",run_name='__main__')"
        cls.process=subprocess.Popen([sys.executable,'-c',bootstrap,str(config)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            end=time.time()+8
            while time.time()<end:
                try:
                    with urllib.request.urlopen(cls.base+'/health',timeout=.3) as r:
                        if r.status==200:break
                except OSError:time.sleep(.03)
            else:raise AssertionError('Test service did not start')
        except Exception:
            cls.process.terminate();cls.process.wait(timeout=5);cls.tmp.cleanup();raise
    @classmethod
    def tearDownClass(cls):
        cls.process.terminate();cls.process.wait(timeout=5);cls.tmp.cleanup()
    @staticmethod
    def body(kind,name):
        return {'kind':kind,'name':name,'path':'~/robo-removal-test','endpoint':'https://example.com','username':'test','password':'TEST-NOT-REAL','bucket':'test-bucket','keysFile':'Endpoint: e2-s3.test.idrivee2.com\nRegion Code: test\nAccess key ID: TEST-NOT-REAL\nSecret Access Key: TEST-NOT-REAL'}
    def call(self,path,body=None,auth=True,token=None):
        headers={'Content-Type':'application/json','X-Robo-Request':'1'}
        if auth:headers['X-Robo-Admin']='TEST-REMOVAL-ADMIN'
        if token:headers['Authorization']='Bearer '+token
        req=urllib.request.Request(self.base+path,data=None if body is None else json.dumps(body).encode(),headers=headers)
        try:r=urllib.request.urlopen(req,timeout=3)
        except urllib.error.HTTPError as e:r=e
        with r:return r.status,json.loads(r.read())
    def create(self,kind='linux'):
        _,data=self.call('/api/groups',{'name':'Setup test','sub':'test-'+secrets.token_hex(4)})
        _,data=self.call('/api/groups/'+data['group']['id']+'/servers',self.body(kind,'Pending '+kind));return data['server']
    def current(self,id):return next(s for s in self.call('/api/state')[1]['servers'] if s['id']==id)
    def disconnect(self,s,**changes):
        return self.call('/api/servers/'+s['id']+'/disconnect-unverified',{'confirmName':s['name'],'keepRemoteFiles':True,**changes})
    def descriptor(self):
        (self.data/'agent-enrollment.json').write_text(json.dumps({'state':'ready','url':'https://checked.example.com','updated':time.time(),'checkedAt':time.time()}))
    def installer(self,s):
        self.descriptor();status,data=self.call('/api/servers/'+s['id']+'/enrollment',{});self.assertEqual(status,200,data)
        url=data.get('download') or data['command'].split()[2].strip("'")
        from urllib.parse import urlsplit,parse_qs
        return parse_qs(urlsplit(url).query)['token'][0]
    def test_pending_all_four_providers_remove_immediately_without_drain(self):
        for kind in ('e2','cloudgate','linux','windows'):
            with self.subTest(kind=kind):
                s=self.create(kind);before=len(self.call('/api/state')[1]['jobs']);start=time.monotonic()
                status,result=self.disconnect(s);self.assertEqual(status,200,result);self.assertFalse(result['remoteFilesChanged']);self.assertLess(time.monotonic()-start,2)
                self.assertEqual(self.current(s['id'])['status'],'removed');self.assertEqual(len(self.call('/api/state')[1]['jobs']),before)
                self.assertTrue(any(g['id']==s['group'] for g in self.call('/api/state')[1]['groups']))
    def test_stuck_draining_recovered_inventory_history_and_files_preserved(self):
        for kind,id in self.legacy.items():
            with self.subTest(kind=kind):
                s=self.current(id);self.assertEqual(s['status'],'draining');self.assertFalse(s['verified'])
                status,result=self.disconnect(s);self.assertEqual(status,200,result)
                current=self.current(id);self.assertEqual(current['status'],'removed');self.assertEqual(current['inventory'],[{'path':'keep.txt','size':9}]);self.assertFalse(current['hasCredentials'])
                jobs=self.call('/api/state')[1]['jobs'];self.assertEqual(next(j for j in jobs if j['server']==id)['state'],'cancelled')
                if kind in ('linux','windows'):
                    self.assertEqual(self.call('/agent/poll',{},auth=False,token='old-agent-'+kind+'-'*40)[0],401)
                    self.assertEqual(self.call('/agent/installer/check',{'platform':kind},auth=False,token='old-installer-'+kind+'-'*40)[0],410)
        self.assertEqual((self.keep/'keep.txt').read_text(),'keep data')
        self.assertEqual(self.call('/agent/installer/check',{'platform':'windows'},auth=False,token='spent-installer-'+'-'*40)[0],409)
    def test_exact_confirmation_acknowledgment_and_admin_required(self):
        s=self.create();self.assertEqual(self.disconnect(s,confirmName='wrong')[0],400)
        self.assertEqual(self.disconnect(s,keepRemoteFiles=False)[0],400)
        self.assertEqual(self.disconnect(s,keepRemoteFiles='true')[0],400)
        self.assertEqual(self.call('/api/servers/'+s['id']+'/disconnect-unverified',{'confirmName':s['name'],'keepRemoteFiles':True},auth=False)[0],401)
        self.assertEqual(self.current(s['id'])['status'],'pending')
    def test_unverified_erase_cannot_start_drain_or_scan(self):
        s=self.create();before=len(self.call('/api/state')[1]['jobs'])
        status,result=self.call('/api/servers/'+s['id']+'/drain',{'mode':'erase','confirmName':s['name']})
        self.assertEqual(status,409,result);self.assertIn('not verified',result['error']);self.assertEqual(self.current(s['id'])['status'],'pending');self.assertEqual(len(self.call('/api/state')[1]['jobs']),before)
    def test_enrolled_without_heartbeat_can_disconnect_and_revoke_installer_and_agent(self):
        for kind in ('linux','windows'):
            s=self.create(kind);token=self.installer(s)
            status,data=self.call('/agent/enroll',{'platform':kind,'root':'D:\\Cloud' if kind=='windows' else '/tmp/robo-test','files':[{'path':'keep.txt','size':9}],'capacity':512000},auth=False,token=token)
            self.assertEqual(status,200,data);agent=data['token'];self.assertFalse(self.current(s['id'])['verified'])
            self.assertEqual(self.disconnect(s)[0],200);self.assertEqual(self.call('/agent/poll',{},auth=False,token=agent)[0],401)
            self.assertEqual(self.call('/api/servers/'+s['id']+'/enrollment',{})[0],409)
            self.assertEqual(self.call('/agent/installer/check',{'platform':kind},auth=False,token=token)[0],409 if kind=='windows' else 410)
    def test_verified_server_cannot_bypass_move_or_erase(self):
        s=self.create();token=self.installer(s);status,data=self.call('/agent/enroll',{'platform':'linux','root':'/tmp/robo-test','files':[{'path':'keep.txt','size':9}],'capacity':512000},auth=False,token=token);self.assertEqual(status,200,data)
        self.assertEqual(self.call('/agent/poll',{},auth=False,token=data['token'])[0],200);self.assertTrue(self.current(s['id'])['verified'])
        self.assertEqual(self.disconnect(s)[0],409);self.assertEqual(self.current(s['id'])['status'],'online')
    def test_registration_and_disconnect_race_never_resurrects_server(self):
        for kind in ('linux','windows'):
            s=self.create(kind);token=self.installer(s)
            with ThreadPoolExecutor(max_workers=2) as pool:
                enrolled=pool.submit(self.call,'/agent/enroll',{'platform':kind,'root':'D:\\Cloud' if kind=='windows' else '/tmp/robo-test','files':[],'capacity':512000},False,token)
                removed=pool.submit(self.disconnect,s)
                code,data=enrolled.result();r_code,r_data=removed.result()
            self.assertEqual(r_code,200,r_data);self.assertIn(code,(200,410),data);self.assertEqual(self.current(s['id'])['status'],'removed')
            if code==200:self.assertEqual(self.call('/agent/poll',{},auth=False,token=data['token'])[0],401)
    def test_first_heartbeat_race_has_one_atomic_winner(self):
        for i in range(8):
            kind='linux' if i%2==0 else 'windows';s=self.create(kind);token=self.installer(s)
            status,data=self.call('/agent/enroll',{'platform':kind,'root':'D:\\Cloud' if kind=='windows' else '/tmp/robo-test','files':[],'capacity':512000},auth=False,token=token);self.assertEqual(status,200,data)
            with ThreadPoolExecutor(max_workers=2) as pool:
                heartbeat=pool.submit(self.call,'/agent/poll',{},False,data['token']);removed=pool.submit(self.disconnect,s);h_code,h_data=heartbeat.result();r_code,r_data=removed.result()
            self.assertIn((h_code,r_code),((200,409),(401,200)),(h_data,r_data))
            current=self.current(s['id']);self.assertEqual(current['status'],'removed' if r_code==200 else 'online');self.assertEqual(current['verified'],r_code!=200)
    def test_new_link_race_does_not_leave_a_live_enrollment_after_disconnect(self):
        for i in range(8):
            s=self.create('linux' if i%2==0 else 'windows');self.descriptor()
            with ThreadPoolExecutor(max_workers=2) as pool:
                renewed=pool.submit(self.call,'/api/servers/'+s['id']+'/enrollment',{});removed=pool.submit(self.disconnect,s);n_code,n_data=renewed.result();r_code,r_data=removed.result()
            self.assertEqual(r_code,200,r_data);self.assertIn(n_code,(200,409),n_data)
            persisted=json.loads((self.data/'storage-state.json').read_text());self.assertFalse(any(e['server']==s['id'] for e in persisted['enrollments']));self.assertEqual(self.current(s['id'])['status'],'removed')
    def test_old_cancel_button_can_remove_never_enrolled_draining_entry(self):
        s=self.current(self.unused['id']);status,result=self.call('/api/servers/'+s['id']+'/cancel-enrollment',{'confirmName':s['name']})
        self.assertEqual(status,200,result);self.assertEqual(self.current(s['id'])['status'],'removed')
    def test_original_tux_is_self_contained_and_attributed(self):
        svg=ET.fromstring((ROOT/'app/static/linux.svg').read_text());image=svg.find('{http://www.w3.org/2000/svg}image');self.assertIsNotNone(image)
        raw=base64.b64decode(image.attrib['href'].split(',',1)[1]);self.assertEqual(hashlib.sha256(raw).hexdigest(),'e4f4c8010312078a37ca1797a8c9eaa5156d0fec407d7875522ca31a3d78c586')
        self.assertEqual(struct.unpack_from('>II',raw,16),(265,314));notice=(ROOT/'docs/licenses/TUX-NOTICE.txt').read_text();self.assertIn('Larry Ewing',notice);self.assertIn('The GIMP',notice)

class RemovalLockSafetyTests(unittest.TestCase):
    def setUp(self):
        import ast,threading
        from core import require
        module=ast.parse((ROOT/'app/server.py').read_text());function=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='disconnect_unverified')
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.store=Store(self.tmp.name);g=self.store.group({'name':'Lock tests','sub':'lock-tests'});self.server=self.store.server(g['id'],{'kind':'linux','name':'Busy worker','path':'~/robo-test'})
        self.lock=threading.RLock();namespace={'require':require,'store':self.store,'locks':{self.server['id']:self.lock}};exec(compile(ast.Module(body=[function],type_ignores=[]),'<actual disconnect_unverified>','exec'),namespace);self.disconnect=namespace['disconnect_unverified'];self.body={'confirmName':self.server['name'],'keepRemoteFiles':True}
    def test_busy_storage_lock_fails_fast_without_waiting_or_mutating(self):
        from core import Problem
        import threading
        ready=threading.Event();release=threading.Event()
        def hold():
            with self.lock:ready.set();release.wait(5)
        thread=threading.Thread(target=hold);thread.start();self.assertTrue(ready.wait(2));start=time.monotonic()
        try:
            with self.assertRaises(Problem) as error:self.disconnect(self.server,self.body)
            self.assertEqual(error.exception.status,409);self.assertLess(time.monotonic()-start,.5);self.assertEqual(self.server['status'],'pending')
        finally:release.set();thread.join(2)
    def test_running_job_cannot_be_hidden_or_race_disconnection(self):
        from core import Problem
        self.store.state['jobs'].append({'id':'test-job','server':self.server['id'],'state':'running'})
        with self.assertRaises(Problem) as error:self.disconnect(self.server,self.body)
        self.assertEqual(error.exception.status,409);self.assertEqual(self.server['status'],'pending');self.assertEqual(self.store.state['jobs'][0]['state'],'running')
    def test_legacy_route_is_not_silently_abandoned_or_group_unpublished(self):
        from core import Problem
        self.server['routePort']=12345
        with self.assertRaises(Problem) as error:self.disconnect(self.server,self.body)
        self.assertEqual(error.exception.status,409);self.assertEqual(self.server['status'],'pending')
