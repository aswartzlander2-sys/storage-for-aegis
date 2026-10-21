"""Automatic descriptor validation and real HTTP command-generation regression tests."""
import base64
import json
from pathlib import Path
import shlex
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from urllib.parse import urlsplit
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
from enrollment import route_status

class DescriptorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
    def write(self, **data):
        (self.root / 'agent-enrollment.json').write_text(json.dumps(data))
    def test_no_descriptor_is_automatic_pending(self):
        result = route_status(self.root)
        self.assertEqual(result['state'], 'pending')
        self.assertIn('automatically', result['detail'])
    def test_ready_needs_valid_https_origin(self):
        for url in ['http://example.com', 'https://user:pass@example.com', 'https://example.com/a', 'https://example.com?x=y', 'https://example.com#x', 'https://']:
            with self.subTest(url=url):
                self.write(state='ready', url=url, updated=1000, checkedAt=1000)
                self.assertNotEqual(route_status(self.root, 1000)['state'], 'ready')
    def test_valid_origin_reads_fresh_and_normalizes_slash(self):
        self.write(state='ready', url='https://agent.example.com/', updated=1000, checkedAt=1000)
        self.assertEqual(route_status(self.root, 1001)['url'], 'https://agent.example.com')
        self.write(state='ready', url='https://changed.example.com', updated=1001, checkedAt=1001)
        self.assertEqual(route_status(self.root, 1002)['url'], 'https://changed.example.com')
    def test_stale_and_future_descriptors_rejected(self):
        for updated, checked in [(800, 800), (1000, 800), (1040, 1040)]:
            self.write(state='ready', url='https://agent.example.com', updated=updated, checkedAt=checked)
            self.assertNotEqual(route_status(self.root, 1000)['state'], 'ready')
    def test_pending_error_never_exposes_unchecked_url(self):
        for state in ['pending', 'error', 'nonsense']:
            self.write(state=state, url='https://unverified.example.com', detail='Waiting for Burrow')
            self.assertEqual(route_status(self.root)['url'], '')
    def test_corrupt_or_wrong_shape_is_pending(self):
        for data in ['{', '[]', 'null', '{"state":"ready","url":"https://example.com","updated":"oops"}']:
            (self.root / 'agent-enrollment.json').write_text(data)
            self.assertEqual(route_status(self.root)['state'], 'pending')

class EnrollmentHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.data = Path(cls.tmp.name)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        cls.base = 'http://127.0.0.1:' + str(port)
        conf = {'id':'robo-storage-aegis','version':'1.0.0','port':port,'bind':'127.0.0.1','host':'burrow','mesh':str(cls.data/'mesh'),'admin_key':'TEST-ONLY-HTTP-KEY','burrow_socket':str(cls.data/'control.sock'),'public_url':'https://obsolete-setting.example.com'}
        config = cls.data / 'config.json'; config.write_text(json.dumps(conf))
        cls.process = subprocess.Popen([sys.executable, str(ROOT/'app/server.py'), str(config)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.time() + 8
            while time.time() < deadline:
                try:
                    with urllib.request.urlopen(cls.base+'/health', timeout=.5) as r:
                        if r.status == 200: break
                except OSError:
                    time.sleep(.05)
            else: raise AssertionError('Test service did not start')
        except Exception:
            cls.process.terminate(); cls.process.wait(timeout=5); cls.tmp.cleanup(); raise
    @classmethod
    def tearDownClass(cls):
        cls.process.terminate(); cls.process.wait(timeout=5); cls.tmp.cleanup()
    def call(self, path, body=None, auth=True):
        headers = {'X-Robo-Request':'1'}
        if auth: headers['X-Robo-Admin']='TEST-ONLY-HTTP-KEY'
        req = urllib.request.Request(self.base+path, data=None if body is None else json.dumps(body).encode(), headers={**headers,'Content-Type':'application/json'})
        try: r=urllib.request.urlopen(req, timeout=4)
        except urllib.error.HTTPError as e: r=e
        return r.status, r.read()
    def route(self, **changes):
        data={'state':'ready','url':'https://checked.example.com','updated':time.time(),'checkedAt':time.time(),'detail':'Verified fixture'}
        data.update(changes); (self.data/'agent-enrollment.json').write_text(json.dumps(data))
    def test_command_is_gated_pinned_and_not_legacy_setting(self):
        status, body=self.call('/api/groups', {'name':'Enrollment regression','sub':'regression','domain':''})
        self.assertEqual(status,200,body); gid=json.loads(body)['group']['id']
        status,body=self.call('/api/groups/'+gid+'/servers',{'kind':'linux','name':'Test worker','path':'~/storage'})
        self.assertEqual(status,200,body); sid=json.loads(body)['server']['id']; endpoint='/api/servers/'+sid+'/enrollment'
        status,body=self.call(endpoint,{})
        self.assertEqual(status,503,body); self.assertNotIn(b'Set Agent enrollment',body)
        self.route(url='http://insecure.example.com');self.assertEqual(self.call(endpoint,{})[0],503)
        self.route(); status,body=self.call(endpoint,{})
        self.assertEqual(status,200,body); command=json.loads(body)['command']
        url=next(arg for arg in shlex.split(command) if arg.startswith('https://'))
        self.assertEqual(urlsplit(url).hostname,'checked.example.com')
        self.assertIn("--proto '=https'",command)
        self.route(url='https://changed.example.com')
        status,script=self.call('/enroll.sh?'+urlsplit(url).query,auth=False)
        self.assertEqual(status,200,script)
        payload=shlex.split(script.decode().splitlines()[-1])[-1]
        self.assertEqual(json.loads(base64.urlsafe_b64decode(payload))['url'],'https://checked.example.com')
        state=json.loads(self.call('/api/state')[1]);self.assertEqual(state['publicUrl'],'https://changed.example.com')
    def test_public_health_is_identity_probe_only(self):
        nonce='a'*32
        status,body=self.call('/agent/health?probe='+nonce,auth=False)
        self.assertEqual(status,200);self.assertEqual(json.loads(body)['probe'],nonce)
        self.assertEqual(json.loads(body)['app'],'robo-storage-aegis')
        self.assertEqual(self.call('/agent/health',auth=False)[0],400)
        self.assertEqual(self.call('/api/state',auth=False)[0],401)
    def test_serves_exact_upstream_stylesheet(self):
        status,body=self.call('/assets/aegis.css')
        self.assertEqual(status,200);self.assertEqual(body,(ROOT/'app/static/aegis.css').read_bytes())

if __name__ == '__main__': unittest.main()
