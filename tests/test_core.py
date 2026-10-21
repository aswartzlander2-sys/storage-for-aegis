import base64
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
from core import *
from backends import E2, CloudGate, AgentBroker, Unix
import agent

class CoreTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store(self.tmp.name)
  self.g=self.store.group({'name':'Tests','sub':'tests','domain':'example.com'})
  self.s=self.store.server(self.g['id'],{'kind':'linux','name':'Linux','path':'~/storage','limit':1000})
 def tearDown(self):self.tmp.cleanup()
 def test_one_gb_allocation_is_not_512_gb_disk_capacity(self):
  self.s['limit']=1_000_000_000
  self.store.update_inventory(self.s,[{'path':'sample','size':10}],512_000_000_000)
  view=self.store.view()['servers'][0]
  self.assertEqual(view['physicalCapacity'],512_000_000_000);self.assertEqual(view['allocationLimit'],1_000_000_000)
  self.assertEqual(view['allocatedCapacity'],1_000_000_000);self.assertEqual(view['remainingAllocation'],999_999_990)
  self.store.save();restarted=Store(self.tmp.name)
  self.assertEqual(restarted.view()['servers'][0]['allocatedCapacity'],1_000_000_000)
  self.store.update_inventory(self.s,[{'path':'existing','size':999_999_999}],512_000_000_000)
  with self.assertRaises(Problem) as error:self.store.check_write(self.s,'new',2)
  self.assertEqual(error.exception.status,507)
  self.store.check_write(self.s,'new',1)
 def test_effective_allocation_uses_smaller_physical_size_and_handles_unknown(self):
  self.assertEqual(capacity_view({'limit':1000,'capacity':100,'used':120})['allocatedCapacity'],100)
  self.assertEqual(capacity_view({'limit':1000,'capacity':100,'used':120})['remainingAllocation'],0)
  self.assertEqual(capacity_view({'limit':1000})['allocatedCapacity'],1000)
  self.assertEqual(capacity_view({'limit':0,'capacity':512_000_000_000})['allocatedCapacity'],512_000_000_000)
  self.assertIsNone(capacity_view({'limit':0})['allocatedCapacity'])
 def test_initial_files_private(self):self.assertEqual(os.stat(self.store.path).st_mode&0o777,0o600)
 def test_state_persists(self):self.assertEqual(Store(self.tmp.name).state['groups'][0]['name'],'Tests')
 def test_corrupt_state_fails_closed(self):
  self.store.path.write_text('{');self.assertRaises(ValueError,Store,self.tmp.name)
 def test_new_group_unique(self):self.assertRaises(Problem,self.store.group,{'name':'Duplicate','sub':'tests','domain':'example.com'})
 def test_dns_rejects_injection(self):
  for s in ['a.b','-bad','bad-','$(whoami)','Upper','x/y','']:
   with self.subTest(s=s):self.assertRaises(Problem,subdomain,s)
 def test_dns_allows_label(self):self.assertEqual(subdomain('studio-1'),'studio-1')
 def test_linux_path_explicit(self):self.assertEqual(linux_path('~/my files'),'~/my files')
 def test_linux_path_rejects_system(self):
  for p in ['/','~/','/etc/passwd','/sys/x','storage','~/../escape']:
   with self.subTest(p=p):self.assertRaises(Problem,linux_path,p)
 def test_relative_paths(self):
  for p in ['../x','/etc/passwd','x/../y','x\\y','.robo-agent/config.json','x\x00y']:
   with self.subTest(p=p):self.assertRaises(Problem,clean_path,p)
 def test_quota_rejects_negative_or_float(self):
  for n in [-1,1.2,True,'5']:self.assertRaises(Problem,quota,n)
 def test_e2_missing_import(self):self.assertRaises(Problem,parse_e2,'')
 def test_e2_fake_fixture_parses(self):
  c=parse_e2('Endpoint: e2-s3.region.idrivee2.com\nRegion Code: region\nAccess key ID: TEST-NOT-REAL\nSecret Access Key: TEST-NOT-REAL')
  self.assertEqual(c['endpoint'],'https://e2-s3.region.idrivee2.com')
 def test_e2_rejects_foreign_endpoint(self):self.assertRaises(Problem,parse_e2,'Endpoint: evil.example\nRegion Code: r\nAccess key ID: x\nSecret Access Key: x')
 def test_store_view_hides_secrets(self):
  self.s.update(credentials={'secret':'private'},agentToken='private');self.store.user(self.g['id'],{'username':'tester','password':'strong-password-1','rules':[{'path':'','access':'write'}]})
  text=json.dumps(self.store.view());self.assertNotIn('private',text);self.assertNotIn('passwordHash',text);self.assertNotIn('agentToken',text)
 def test_scrypt(self):
  h=password_hash('strong-password-1');self.assertTrue(password_check('strong-password-1',h));self.assertFalse(password_check('incorrect',h))
 def test_short_password(self):self.assertRaises(Problem,password_hash,'weak')
 def test_permission_most_specific(self):
  u={'rules':[{'path':'','access':'write'},{'path':'private','access':'none'},{'path':'private/public.txt','access':'read'}]}
  self.assertFalse(visible(u,'private/x'));self.assertTrue(visible(u,'private/public.txt'));self.assertFalse(visible(u,'private/public.txt','write'));self.assertTrue(visible(u,'private-other/a','write'))
 def test_permission_default_deny(self):self.assertFalse(visible({'rules':[]},'x'))
 def test_user_duplicate_path_rejected(self):self.assertRaises(Problem,self.store.user,self.g['id'],{'username':'tester','password':'strong-password-1','rules':[{'path':'','access':'write'},{'path':'','access':'read'}]})
 def test_password_rotation_preserves_other_users(self):
  self.store.user(self.g['id'],{'username':'tester','password':'strong-password-1','rules':[{'path':'','access':'write'}]})
  self.store.user(self.g['id'],{'username':'tester','password':'strong-password-2','rules':[{'path':'','access':'read'}]})
  self.assertEqual(len(self.store.state['users']),1);self.assertTrue(password_check('strong-password-2',self.store.state['users'][0]['passwordHash']))
 def test_username_can_change_without_password_loss(self):
  u=self.store.user(self.g['id'],{'username':'before','password':'strong-password-1','rules':[{'path':'','access':'write'}]})
  self.store.user(self.g['id'],{'id':u['id'],'username':'after','rules':[{'path':'','access':'read'}]})
  saved=self.store.get('users',u['id']);self.assertEqual(saved['username'],'after');self.assertTrue(password_check('strong-password-1',saved['passwordHash']))
 def test_inventory_type_totals(self):
  self.store.update_inventory(self.s,[{'path':'video.mp4','size':40},{'path':'x.py','size':10}]);self.assertEqual(self.s['used'],50);self.assertEqual(self.s['types']['video'],40)
 def test_invalid_inventory_rejected(self):self.assertRaises(Problem,self.store.update_inventory,self.s,[{'path':'../x','size':1}])
 def test_server_quota_enforced(self):
  self.store.update_inventory(self.s,[{'path':'x','size':900}]);self.assertRaises(Problem,self.store.check_write,self.s,'new',101);self.store.check_write(self.s,'new',100)
 def test_overwrite_charged_delta(self):
  self.store.update_inventory(self.s,[{'path':'x','size':900}]);self.store.check_write(self.s,'x',1000)
 def test_partition_quota_enforced(self):
  self.store.update_inventory(self.s,[{'path':'p/x','size':90}]);self.s['partitions']=[{'path':'p','limit':100}];self.assertRaises(Problem,self.store.check_write,self.s,'p/y',11)
 def test_draining_blocks_writes(self):
  self.s.update(verified=True,status='draining');self.assertRaises(Problem,self.store.check_write,self.s,'x',1)
 def test_readonly_blocks_writes(self):
  self.s.update(verified=True,readOnly=True);self.assertRaises(Problem,self.store.check_write,self.s,'x',1)
 def test_unverified_blocks_writes(self):self.assertRaises(Problem,self.store.check_write,self.s,'x',1)
 def test_full_inventory_preserves_draining(self):
  self.s['status']='draining';self.store.update_inventory(self.s,[]);self.assertEqual(self.s['status'],'draining')
 def test_interrupted_job_not_resumed(self):
  self.store.state['jobs']=[{'id':'x','state':'running'}];self.store.save();self.assertEqual(Store(self.tmp.name).state['jobs'][0]['state'],'interrupted')
 def test_nested_budgets_not_double_counted(self):
  validate_partitions([{'path':'a','limit':100},{'path':'a/b','limit':60},{'path':'a/c','limit':40}],100)
 def test_parent_reduction_below_child_rejected(self):
  self.assertRaises(Problem,validate_partitions,[{'path':'a','limit':50},{'path':'a/b','limit':60}],100)
 def test_child_budget_sum_cannot_exceed_parent(self):
  self.assertRaises(Problem,validate_partitions,[{'path':'a','limit':100},{'path':'a/b','limit':60},{'path':'a/c','limit':60}],100)
 def test_agent_create_read_delete(self):
  root=Path(self.tmp.name)/'files';root.mkdir();agent.execute(str(root),{'op':'write','path':'nested/x.txt','data':base64.b64encode(b'hello').decode()});r=agent.execute(str(root),{'op':'read','path':'nested/x.txt'});self.assertEqual(base64.b64decode(r['data']),b'hello');agent.execute(str(root),{'op':'delete','path':'nested/x.txt'});self.assertFalse((root/'nested/x.txt').exists())
 def test_agent_symlink_cannot_escape(self):
  root=Path(self.tmp.name)/'files';root.mkdir();(root/'escape').symlink_to('/etc');self.assertRaises(OSError,agent.execute,str(root),{'op':'read','path':'escape/passwd'})
 def test_agent_file_symlink_no_read(self):
  root=Path(self.tmp.name)/'files';root.mkdir();(root/'x').symlink_to('/etc/passwd');self.assertRaises(OSError,agent.execute,str(root),{'op':'read','path':'x'})
 def test_agent_traversal_rejected(self):
  for p in ['../x','/x','x//y','.robo-agent/config.json']:self.assertRaises(ValueError,agent.parts,p)
 def test_scan_excludes_agent_metadata(self):
  root=Path(self.tmp.name)/'files';root.mkdir();(root/'.robo-agent').mkdir();(root/'.robo-agent/secret').write_text('secret');(root/'visible').write_text('hi');self.assertEqual(agent.scan(str(root))['files'],[{'path':'visible','size':2}])
 def test_broker_ownership(self):
  b=AgentBroker();self.assertRaises(Problem,b.finish,'unknown','unknown',{})
 def test_unix_socket_realpath(self):
  p=Path(self.tmp.name);(p/'link').symlink_to(p/'actual');self.assertEqual(Unix(str(p/'link')).socket_path,str(p/'actual'))
 def test_private_storage_endpoint_rejected(self):self.assertRaises(Problem,public_https,'https://127.0.0.1')
 def test_non_https_endpoint_rejected(self):self.assertRaises(Problem,public_https,'http://example.com')
 def test_e2_signing_contains_no_secret_in_url(self):
  s={'credentials':{'endpoint':'https://e2-s3.region.idrivee2.com','region':'region','access':'TESTID','secret':'SECRET-NOT-REAL','bucket':'bucket','prefix':'safe'}}
  with patch('backends.request',return_value=b'') as req:E2(s).write('x.txt',b'test')
  args=req.call_args.args;self.assertEqual(args[0],'https://e2-s3.region.idrivee2.com/bucket/safe/x.txt');self.assertIn('AWS4-HMAC-SHA256',args[3]['Authorization']);self.assertNotIn('SECRET-NOT-REAL',str(args))

if __name__=='__main__':unittest.main(verbosity=2)
