"""Group inheritance regressions, read-only snapshots and real HTTP/Unix control calls."""
import base64
from http.server import BaseHTTPRequestHandler
import json
from pathlib import Path
import secrets
import socketserver
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
from routing import routing_view
from core import Store, Problem
import test_enrollment

class RouteViewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.addCleanup(self.tmp.cleanup)
    def state(self):return {'groups':[{'id':'a'*16,'url':'','routePort':7000}], 'servers':[{'id':'b'*16,'group':'a'*16,'verified':True,'status':'online','url':'https://old-independent.example.com'}]}
    def write(self,**route):
        data={'port':7000,'url':'https://group.example.com','proposedUrl':'https://group.example.com','state':'ready','base':'example.com','checkedAt':1000,**route}
        (self.root/'published-routes.json').write_text(json.dumps({'updated':1000,'groups':{'a'*16:data}}))
    def test_server_url_is_group_scoped_and_view_is_read_only(self):
        self.write();before=(self.root/'published-routes.json').read_bytes()
        view=routing_view(self.root,self.state(),1001)
        self.assertEqual(view['servers'][0]['url'],'https://group.example.com/s/'+'b'*16+'/')
        self.assertTrue(view['servers'][0]['inheritsGroupAddress'])
        self.assertEqual(before,(self.root/'published-routes.json').read_bytes())
    def test_pending_route_never_retains_old_server_domain(self):
        self.write(state='pending',url='')
        view=routing_view(self.root,self.state(),1001)
        self.assertEqual(view['servers'][0]['url'],'');self.assertEqual(view['groups'][0]['routeState'],'pending')
    def test_stale_snapshot_is_not_ready(self):
        self.write();view=routing_view(self.root,self.state(),1200)
        self.assertEqual(view['servers'][0]['url'],'');self.assertNotEqual(view['groups'][0]['routeState'],'ready')
    def test_removed_and_unverified_servers_have_no_public_link(self):
        self.write()
        for fields in ({'status':'removed'},{'verified':False}):
            state=self.state();state['servers'][0].update(fields)
            self.assertEqual(routing_view(self.root,state,1001)['servers'][0]['url'],'')
    def test_corrupt_snapshot_fails_closed(self):
        (self.root/'published-routes.json').write_text('{')
        self.assertEqual(routing_view(self.root,self.state(),1000)['servers'][0]['url'],'')

    def test_old_unchecked_prefixed_snapshot_is_blocked_immediately(self):
        self.write(useDefaultTunnel=False,base='apps.example.com')
        state=self.state();state['groups'][0].update(useDefaultTunnel=False,base='apps.example.com',sub='group')
        view=routing_view(self.root,state,1001)
        self.assertEqual(view['groups'][0]['routeState'],'blocked');self.assertEqual(view['servers'][0]['url'],'');self.assertEqual(view['groups'][0]['proposedUrl'],'')
    def test_corrupt_root_route_shape_fails_closed(self):
        (self.root/'published-routes.json').write_text(json.dumps({'updated':1000,'groups':{'a'*16:['corrupt']}}))
        state=self.state();state['groups'][0].update(useDefaultTunnel=False,base='example.com',sub='group')
        self.assertEqual(routing_view(self.root,state,1001)['groups'][0]['routeState'],'blocked')
    def test_root_proof_must_match_exact_requested_address(self):
        state=self.state();state['groups'][0].update(useDefaultTunnel=False,base='example.com',sub='group')
        self.write(useDefaultTunnel=False,rootDomain='example.com')
        self.assertEqual(routing_view(self.root,state,1001)['groups'][0]['routeState'],'ready')
        self.write(useDefaultTunnel=False,rootDomain='example.com',url='https://group.apps.example.com')
        self.assertEqual(routing_view(self.root,state,1001)['groups'][0]['routeState'],'blocked')

class GroupModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.store=Store(self.tmp.name)
    def test_default_mode_ignores_old_manual_nested_address(self):
        g=self.store.group({'name':'Default','sub':'default','domain':'wrong.invalid','tunnelSub':'unconfigured'})
        self.assertTrue(g['useDefaultTunnel']);self.assertEqual(g['base'],'');self.assertEqual(g['tunnelSub'],'')
    def test_checkbox_is_boolean_and_default_subdomain_is_unique(self):
        with self.assertRaises(Problem):self.store.group({'name':'Invalid','sub':'invalid','useDefaultTunnel':'false'})
        self.store.group({'name':'First','sub':'same','domain':'a.invalid'})
        with self.assertRaises(Problem):self.store.group({'name':'Second','sub':'same','domain':'b.invalid'})
    def test_explicit_custom_base_is_preserved(self):
        g=self.store.group({'name':'Custom','sub':'custom','base':'example.com','useDefaultTunnel':False})
        self.assertFalse(g['useDefaultTunnel']);self.assertEqual(g['base'],'example.com')

class RoutingHTTPTests(test_enrollment.EnrollmentHTTPTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass();cls.published=[]
        class Control(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))))
                assert self.headers['X-Burrow-Client']=='robo-storage-aegis/1.1.0'
                if self.path.endswith('/enrollment'):
                    self.send_response(200);self.end_headers();self.wfile.write(b'{"state":"pending"}');return
                assert self.path.endswith('/publish'),self.path
                cls.published.append(body)
                if body.get('useDefaultTunnel') is False and body.get('base')!='example.com':
                    self.send_response(400);self.end_headers();self.wfile.write(b'{"error":"Select a configured tunnel domain or use default Burrow tunnel."}');return
                base='apps.example.com' if body['useDefaultTunnel'] else body['base']
                route={'rootDomain':None if body['useDefaultTunnel'] else base,'port':7000,'url':'https://'+body['sub']+'.'+base,'state':'ready','base':base,'checkedAt':time.time(),'useDefaultTunnel':body['useDefaultTunnel']}
                (cls.data/'published-routes.json').write_text(json.dumps({'updated':time.time(),'groups':{body['group']:route}}))
                self.send_response(200);self.end_headers();self.wfile.write(json.dumps(route).encode())
        cls.control=socketserver.UnixStreamServer(str(cls.data/'control.sock'),Control)
        cls.thread=threading.Thread(target=cls.control.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.control.shutdown();cls.control.server_close();cls.thread.join();super().tearDownClass()
    def group(self,**fields):
        body={'name':'Routing test','sub':'test-'+secrets.token_hex(4),**fields}
        status,data=self.call('/api/groups',body);self.assertEqual(status,200,data);return json.loads(data)['group']
    def worker(self,group):
        status,data=self.call('/api/groups/'+group['id']+'/servers',{'name':'Worker','kind':'linux','path':'~/test-worker'})
        self.assertEqual(status,200,data);return json.loads(data)['server']
    def verify(self,server):
        import shlex
        from urllib.parse import urlsplit,parse_qs
        self.route();status,data=self.call('/api/servers/'+server['id']+'/enrollment',{});self.assertEqual(status,200,data)
        url=next(arg for arg in shlex.split(json.loads(data)['command']) if arg.startswith('https://'))
        token=parse_qs(urlsplit(url).query)['token'][0]
        def agent(path,token,body):
            req=urllib.request.Request(self.base+path,data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
            with urllib.request.urlopen(req,timeout=4) as r:return json.load(r)
        result=agent('/agent/enroll',token,{'files':[],'root':'/synthetic/worker','hostname':'test-worker','capacity':1000})
        agent('/agent/poll',result['token'],{})
    def test_default_group_launch_does_not_compare_legacy_nested_domain(self):
        g=self.group(domain='wrong.invalid',tunnelSub='mismatch')
        self.call('/api/groups/'+g['id']+'/users',{'username':'test-user','password':'SYNTHETIC-test-password','enabled':True,'rules':[{'path':'','access':'write'}]})
        status,body=self.call('/api/groups/'+g['id']+'/launch',{'domain':'stale.invalid','tunnelSub':'wrong'})
        self.assertEqual(status,200,body);record=self.published[-1]
        self.assertEqual(record['key'],g['id']);self.assertTrue(record['useDefaultTunnel']);self.assertEqual(record['base'],'');self.assertEqual(record['server'],'')
    def test_server_launch_ignores_all_injected_address_fields(self):
        g=self.group();s=self.worker(g)
        self.call('/api/groups/'+g['id']+'/users',{'username':'test-user','password':'SYNTHETIC-test-password','enabled':True,'rules':[{'path':'','access':'write'}]})
        self.verify(s)
        status,body=self.call('/api/servers/'+s['id']+'/launch',{'sub':'wrong','base':'wrong.invalid','domain':'wrong.invalid','useDefaultTunnel':False})
        self.assertEqual(status,200,body);result=json.loads(body);record=self.published[-1]
        self.assertEqual(record['sub'],g['sub']);self.assertEqual(record['key'],g['id']);self.assertTrue(record['useDefaultTunnel']);self.assertEqual(record['server'],'')
        self.assertEqual(result['url'],result['groupUrl']+'/s/'+s['id']+'/')
        state=json.loads(self.call('/api/state')[1]);view=next(sv for sv in state['servers'] if sv['id']==s['id'])
        self.assertEqual(view['url'],result['url'])
    def test_unverified_server_cannot_publish(self):
        g=self.group();s=self.worker(g);before=len(self.published)
        self.assertEqual(self.call('/api/servers/'+s['id']+'/launch',{})[0],409)
        self.assertEqual(len(self.published),before)
    def test_route_probe_is_public_but_file_browser_stays_authenticated(self):
        g=self.group();nonce='a'*32
        status,body=self.call('/g/'+g['id']+'/route-health?probe='+nonce,auth=False)
        self.assertEqual(status,200);self.assertEqual(json.loads(body)['group'],g['id']);self.assertEqual(json.loads(body)['probe'],nonce)
        self.assertEqual(self.call('/g/'+g['id']+'/',auth=False)[0],401)
    def test_robo_assets_and_preview_csp_are_group_authenticated(self):
        g=self.group();s=self.worker(g);self.verify(s)
        self.call('/api/groups/'+g['id']+'/users',{'username':'ui-check','password':'SYNTHETIC-ui-check-password','enabled':True,'rules':[{'path':'','access':'write'}]})
        self.call('/api/servers/'+s['id']+'/settings',{'name':s['name'],'limit':100,'readOnly':True})
        token=base64.b64encode(b'ui-check:SYNTHETIC-ui-check-password').decode()
        def get(path):
            return urllib.request.urlopen(urllib.request.Request(self.base+'/g/'+g['id']+'/'+path,headers={'Authorization':'Basic '+token}),timeout=4)
        with get('') as r:
            html=r.read().decode();policies=r.headers.get_all('Content-Security-Policy')
            self.assertEqual(len(policies),1);self.assertIn("frame-src blob:",policies[0]);self.assertIn("script-src 'self'",policies[0]);self.assertIn("object-src 'none'",policies[0])
            self.assertIn('assets/robo.css',html);self.assertNotIn('cdn.',html);self.assertNotIn('S3_AK',html)
        for resource in ('assets/robo.css','assets/robo-theme.js','assets/files.js'):
            with get(resource) as r:self.assertEqual(r.status,200)
        with get('api/files') as r:
            server=json.load(r)['servers'][0];self.assertTrue(server['readOnly']);self.assertEqual(server['allocatedCapacity'],100);self.assertEqual(server['physicalCapacity'],1000)
        with urllib.request.urlopen(urllib.request.Request(self.base+'/',headers={'X-Robo-Admin':'TEST-ONLY-HTTP-KEY'})) as r:
            policy=r.headers['Content-Security-Policy'];self.assertNotIn('blob:',policy)
    def test_custom_checkbox_is_respected_without_changing_global_naming(self):
        g=self.group(useDefaultTunnel=False,base='example.com')
        self.call('/api/groups/'+g['id']+'/users',{'username':'test-user','password':'SYNTHETIC-test-password','enabled':True,'rules':[{'path':'','access':'write'}]})
        self.assertEqual(self.call('/api/groups/'+g['id']+'/launch',{})[0],200)
        self.assertFalse(self.published[-1]['useDefaultTunnel']);self.assertEqual(self.published[-1]['base'],'example.com')

if __name__=='__main__':unittest.main()
