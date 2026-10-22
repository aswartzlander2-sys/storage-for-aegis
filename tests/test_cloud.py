"""Gateway rename transactions and exact-reference integration invariants."""
from pathlib import Path
import json,sys,tempfile,threading,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'app'))
from core import Store,Problem
from cloud import rename
class CloudTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.store=Store(self.tmp.name)
        g=self.store.group({'name':'Cloud','sub':'cloud'})
        self.s=self.store.server(g['id'],{'kind':'linux','name':'Worker','path':'~/cloud','limit':1000})
        self.files={'old.txt':b'content'};self.user={'rules':[{'path':'','access':'write'}]};self.lock={self.s['id']:threading.RLock()}
        test=self
        class Memory:
            def read(self,p):return test.files[p]
            def delete(self,p):del test.files[p]
        self.backend=Memory();self.addCleanup(patch.stopall);patch('cloud.backend',return_value=self.backend).start();self.scan(self.s)
    def scan(self,s):self.store.update_inventory(s,[{'path':p,'size':len(v)} for p,v in self.files.items()],512_000_000_000)
    def upload(self,s,p,data):self.scan(s);self.store.check_write(s,p,len(data));self.files[p]=data;self.scan(s)
    def run_rename(self,**body):return rename(self.store,None,self.lock,self.scan,self.upload,self.s,self.user,{'path':'old.txt','newPath':'new.txt',**body})
    def test_rename_verifies_copy_and_removes_source(self):
        self.assertTrue(self.run_rename()['ok']);self.assertEqual(self.files,{'new.txt':b'content'})
    def test_folder_marker_and_children_rename(self):
        self.files={'dir/.keep':b'','dir/child.txt':b'hello'};self.run_rename(path='dir/',newPath='renamed/',folder=True)
        self.assertEqual(self.files,{'renamed/.keep':b'','renamed/child.txt':b'hello'})
    def test_existing_destination_is_not_overwritten(self):
        self.files['new.txt']=b'existing'
        with self.assertRaises(Problem) as e:self.run_rename()
        self.assertEqual(e.exception.status,409);self.assertEqual(self.files['old.txt'],b'content');self.assertEqual(self.files['new.txt'],b'existing')
    def test_quota_failure_retains_source(self):
        self.s['limit']=7
        with self.assertRaises(Problem) as e:self.run_rename()
        self.assertEqual(e.exception.status,507);self.assertEqual(self.files,{'old.txt':b'content'})
    def test_read_only_permission_rejects_before_copy(self):
        self.user={'rules':[{'path':'','access':'read'}]}
        with self.assertRaises(Problem) as e:self.run_rename()
        self.assertEqual(e.exception.status,403);self.assertEqual(self.files,{'old.txt':b'content'})
    def test_changed_source_is_retained(self):
        normal=self.backend.read;calls=0
        def read(p):
            nonlocal calls
            if p=='old.txt':
                calls+=1
                if calls==2:self.files[p]=b'changed'
            return normal(p)
        self.backend.read=read
        with self.assertRaises(Problem) as e:self.run_rename()
        self.assertEqual(e.exception.status,409);self.assertEqual(self.files['old.txt'],b'changed')
    def test_reference_fidelity_and_stable_identity(self):
        audit=json.loads((ROOT/'docs/REFERENCE-FIDELITY.json').read_text())
        self.assertTrue(audit['styleBlocksPreservedByteForByte']);self.assertTrue(audit['allOriginalControlIdsPreserved']);self.assertEqual(len(audit['sourceStyleSha256']),19)
        manifest=json.loads((ROOT/'forge-addon.json').read_text());self.assertEqual(manifest['id'],'robo-storage-aegis');self.assertEqual(manifest['name'],'Robo Cloud')
        ui=(ROOT/'app/static/cloud-ui.js').read_text();self.assertIn('sandbox="" id="htmlRenderIframe"',ui);self.assertIn('isEvalSupported: false',ui)
    def test_visible_empty_partition_metadata_is_acl_filtered(self):
        from cloud import visible_partitions,file_view
        self.s['partitions']=[{'path':'empty','name':'Empty','limit':10},{'path':'private','name':'Hidden label','limit':10}]
        self.user['rules'].append({'path':'private','access':'none'})
        self.assertEqual([p['path'] for p in visible_partitions(self.s,self.user)],['empty'])
        self.user['username']='tester'
        data=file_view(self.store,[self.s],self.s['id'],self.user,'Cloud')
        self.assertEqual(data['partitions'][0]['path'],'empty');self.assertNotIn('Hidden label',json.dumps(data))
    def test_registered_partition_folder_cannot_be_renamed(self):
        self.s['partitions']=[{'path':'dir/child','name':'Child','limit':10}]
        self.files={'dir/child/a.txt':b'a'}
        with self.assertRaises(Problem) as e:self.run_rename(path='dir/',newPath='new/',folder=True)
        self.assertEqual(e.exception.status,409);self.assertEqual(self.files,{'dir/child/a.txt':b'a'})
