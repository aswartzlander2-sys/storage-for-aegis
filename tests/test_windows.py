"""Real HTTP protocol/PE tests. These do NOT execute the GUI on native Windows."""
import concurrent.futures
import hashlib
import secrets
import json
from pathlib import Path
import struct
import unittest
import urllib.request
import urllib.error
from urllib.parse import urlsplit,parse_qs
import test_enrollment
from tools.pe_resources import resources

class WindowsHTTPTests(unittest.TestCase):
    setUpClass=classmethod(test_enrollment.EnrollmentHTTPTests.setUpClass.__func__)
    tearDownClass=classmethod(test_enrollment.EnrollmentHTTPTests.tearDownClass.__func__)
    call=test_enrollment.EnrollmentHTTPTests.call
    route=test_enrollment.EnrollmentHTTPTests.route
    def create(self):
        status,body=self.call('/api/groups',{'name':'Windows HTTP test','sub':'windows-'+secrets.token_hex(4)})
        self.assertEqual(status,200,body);gid=json.loads(body)['group']['id']
        status,body=self.call('/api/groups/'+gid+'/servers',{'kind':'windows','name':'Windows folder','limit':1_000_000_000})
        self.assertEqual(status,200,body);s=json.loads(body)['server'];self.assertEqual(s['path'],'')
        self.route();status,body=self.call('/api/servers/'+s['id']+'/enrollment',{})
        self.assertEqual(status,200,body);r=json.loads(body);self.assertNotIn('command',r)
        return s,r,parse_qs(urlsplit(r['download']).query)['token'][0]
    def public(self,path,body=None,token=''):
        req=urllib.request.Request(self.base+path,data=None if body is None else json.dumps(body).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        try:r=urllib.request.urlopen(req,timeout=5)
        except urllib.error.HTTPError as e:r=e
        return r.status,r.read()
    def test_download_pe_pinned_and_not_consumed(self):
        s,r,token=self.create();self.route(url='https://different.example.com');query='?'+urlsplit(r['download']).query
        status,exe=self.public('/enroll.exe'+query);self.assertEqual(status,200,exe[:100]);self.assertTrue(exe.startswith(b'MZ'))
        with urllib.request.urlopen(self.base+'/enroll.exe'+query) as download:self.assertEqual(download.headers['Content-Disposition'], 'attachment; filename="Robo Cloud Enrollment.exe"')
        pe=struct.unpack_from('<I',exe,0x3c)[0];self.assertEqual(exe[pe:pe+4],b'PE\0\0');self.assertEqual(struct.unpack_from('<H',exe,pe+4)[0],0x8664)
        self.assertEqual(struct.unpack_from('<H',exe,pe+24+68)[0],2) # GUI subsystem, not console.
        magic=b'ROBOCLOUD-ENROLL-V1';self.assertTrue(exe.endswith(magic));n=struct.unpack('<I',exe[-len(magic)-4:-len(magic)])[0];payload=json.loads(exe[-len(magic)-4-n:-len(magic)-4]);self.assertEqual(payload['url'],'https://checked.example.com');self.assertEqual(payload['enrollment'],token)
        base=(Path(__file__).resolve().parents[1]/'app/windows/Robo Cloud Enrollment.exe').read_bytes();self.assertEqual(hashlib.sha256(exe[:-len(magic)-4-n]).digest(),hashlib.sha256(base).digest())
        self.assertEqual(self.public('/enroll.exe'+query),(200,exe))
        self.assertEqual(self.public('/enroll.sh'+query)[0],400)
        for _ in range(2):self.assertEqual(self.public('/agent/installer/check',{'platform':'windows'},token)[0],200)
    def test_atomic_single_use_platform_probe_heartbeat_and_tombstone(self):
        s,r,token=self.create()
        body={'platform':'windows','root':'D:\\DedicatedFolder','capacity':512_000_000_000,'files':[{'path':'notes.txt','size':4}],'hostname':'Windows-fixture'}
        self.assertEqual(self.public('/agent/enroll',{**body,'platform':'linux'},token)[0],400)
        for override in [{'root':'C:\\'},{'root':'\\\\server\\share'},{'capacity':-1},{'files':[{'path':'../escape','size':4}]}]:self.assertEqual(self.public('/agent/enroll',{**body,**override},token)[0],400)
        self.assertEqual(self.public('/agent/installer/check',{'platform':'windows'},token)[0],200)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:self.public('/agent/enroll',body,token),range(2)))
        self.assertEqual(sorted(status for status,_ in results),[200,409])
        success=json.loads(next(b for st,b in results if st==200));used=json.loads(next(b for st,b in results if st==409));self.assertEqual(used,{'code':'installer_used','error':'This Installer was already used on another system.'})
        status,view=self.call('/api/state');current=next(x for x in json.loads(view)['servers'] if x['id']==s['id']);self.assertFalse(current['verified']);self.assertFalse(current['online']);self.assertEqual(current['allocatedCapacity'],1_000_000_000)
        self.assertEqual(self.public('/agent/poll',{},success['token'])[0],200)
        status,view=self.call('/api/state');current=next(x for x in json.loads(view)['servers'] if x['id']==s['id']);self.assertTrue(current['verified']);self.assertTrue(current['online']);self.assertEqual(current['path'],body['root'])
        self.assertEqual(self.call('/api/servers/'+s['id']+'/cancel-enrollment',{'confirmName':s['name']})[0],409)
        # Regeneration removes old active records but never loses consumed-token hashes.
        self.assertEqual(self.call('/api/servers/'+s['id']+'/enrollment',{})[0],200)
        self.assertEqual(json.loads(self.public('/agent/installer/check',{'platform':'windows'},token)[1]),used)
        state=json.loads((self.data/'storage-state.json').read_text());self.assertIn(hashlib.sha256(token.encode()).hexdigest(),state['usedInstallers']);self.assertNotIn(token,json.dumps(state))
    def test_unknown_installer_is_expired_not_used(self):
        st,body=self.public('/agent/installer/check',{'platform':'windows'},'unknown-token')
        self.assertEqual(st,410);self.assertNotIn('installer_used',body.decode())

    def test_cancel_unused_enrollment_without_storage_operations(self):
        s,r,token=self.create()
        path='/api/servers/'+s['id']+'/cancel-enrollment'
        self.assertEqual(self.call(path,{'confirmName':'wrong'})[0],400)
        self.assertEqual(self.public('/agent/installer/check',{'platform':'windows'},token)[0],200)
        self.assertEqual(self.call(path,{'confirmName':s['name']})[0],200)
        self.assertEqual(self.public('/agent/installer/check',{'platform':'windows'},token)[0],410)

    def test_full_worker_stays_full_after_first_heartbeat(self):
        s,r,token=self.create()
        status,body=self.public('/agent/enroll',{'platform':'windows','root':'D:\\Cloud','capacity':512_000_000_000,'files':[{'path':'large.bin','size':1_000_000_000}]},token)
        self.assertEqual(status,200,body);agent=json.loads(body)['token']
        self.assertEqual(self.public('/agent/poll',{},agent)[0],200)
        status,body=self.call('/api/state');state=json.loads(body);current=next(x for x in state['servers'] if x['id']==s['id'])
        self.assertEqual(current['status'],'full');self.assertTrue(current['verified']);self.assertNotIn('usedInstallers',state)
    def test_new_static_controls_and_provider_icon_are_served(self):
        for path in ['/assets/dashboard-controls.css','/assets/windows.svg']:
            status,body=self.call(path);self.assertEqual(status,200,body);self.assertTrue(body)

    def test_replacement_uses_same_folder_and_rotates_only_after_success(self):
        s,r,token=self.create();probe={'platform':'windows','root':'D:\\Cloud','capacity':512_000_000_000,'files':[]}
        st,raw=self.public('/agent/enroll',probe,token);self.assertEqual(st,200,raw);old=json.loads(raw)['token']
        st,raw=self.call('/api/servers/'+s['id']+'/enrollment',{});self.assertEqual(st,200,raw);new=parse_qs(urlsplit(json.loads(raw)['download']).query)['token'][0]
        self.assertEqual(self.public('/agent/enroll',{**probe,'root':'E:\\Different'},new)[0],409)
        self.assertEqual(self.public('/agent/poll',{},old)[0],200)
        self.assertEqual(self.public('/agent/installer/check',{'platform':'windows'},new)[0],200)
        self.assertEqual(self.public('/agent/enroll',probe,new)[0],200)
        self.assertEqual(self.public('/agent/poll',{},old)[0],401)

class WindowsBrandingTests(unittest.TestCase):
    def test_embedded_product_name_and_robo_icon(self):
        root=Path(__file__).resolve().parents[1]
        pe=(root/'app/windows/Robo Cloud Enrollment.exe').read_bytes();r=resources(pe)
        version=next(v for k,v in r.items() if k[0]==16)
        def block(start):
            length,values,type_=struct.unpack_from('<HHH',version,start);end=start+length;cursor=start+6
            finish=cursor
            while version[finish:finish+2]!=b'\0\0':finish+=2
            key=version[cursor:finish].decode('utf-16le');cursor=(finish+2+3)&~3
            value=version[cursor:cursor+(values*2 if type_==1 else values)];cursor=(cursor+len(value)+3)&~3
            children=[]
            while cursor+6<=end:
                size=struct.unpack_from('<H',version,cursor)[0]
                if not size:break
                children.append(block(cursor));cursor=(cursor+size+3)&~3
            return key,value,children
        strings={}
        def collect(b):
            k,v,children=b
            if v:
                try:strings[k]=v.decode('utf-16le').rstrip('\0')
                except UnicodeError:pass
            for c in children:collect(c)
        collect(block(0))
        for key in ['ProductName','FileDescription','InternalName']:self.assertEqual(strings[key],'Robo Cloud Enrollment')
        self.assertEqual(strings['OriginalFilename'],'Robo Cloud Enrollment.exe')
        self.assertEqual(strings['CompanyName'],'Robo Universal')
        group=r[(14,'APP',0)];reserved,kind,count=struct.unpack_from('<HHH',group);self.assertEqual((reserved,kind),(0,1));self.assertEqual(count,5)
        sizes=[]
        for i in range(count):
            w,h,colors,reserved,planes,bits,n,id_=struct.unpack_from('<BBBBHHIH',group,6+14*i)
            sizes.append(w or 256);self.assertEqual(w,h);self.assertEqual(len(r[(3,id_,0)]),n)
        self.assertEqual(sorted(sizes),[16,32,48,64,256])
        record=json.loads((root/'docs/WINDOWS-BUILD.json').read_text());self.assertEqual(record['iconSourceSha256'],hashlib.sha256((root/'logo.png').read_bytes()).hexdigest())
        self.assertIn('const appName = "Robo Cloud Enrollment"',(root/'windows-worker/worker.go').read_text())
