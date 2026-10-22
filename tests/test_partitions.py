"""Atomic staged logical partition plans: no backend I/O or disk operations."""
import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from partitions import apply_plan
from core import Problem
class PartitionPlanTests(unittest.TestCase):
 def setUp(self):self.s={'limit':1000,'capacity':5000,'partitions':[{'id':'existing','path':'projects','name':'Projects','limit':600}],'inventory':[{'path':'projects/a.txt','size':100}]}
 def body(self,rows):return {'confirm':True,'expected':copy.deepcopy(self.s['partitions']),'expectedLimit':self.s['limit'],'partitions':rows}
 def test_batch_create_resize_and_preserve_identity(self):
  apply_plan(self.s,self.body([{'path':'projects','name':'Work','limit':500},{'path':'empty','name':'Empty','limit':500}]))
  self.assertEqual(self.s['partitions'][0]['id'],'existing');self.assertEqual(len(self.s['partitions']),2);self.assertEqual(self.s['inventory'][0]['size'],100)
 def test_plan_requires_review_confirmation(self):
  b=self.body([]);b['confirm']=False
  with self.assertRaises(Problem):apply_plan(self.s,b)
  self.assertEqual(len(self.s['partitions']),1)
 def test_conflicting_edit_returns_409(self):
  b=self.body([]);self.s['partitions'][0]['limit']=700
  with self.assertRaises(Problem) as e:apply_plan(self.s,b)
  self.assertEqual(e.exception.status,409);self.assertEqual(self.s['partitions'][0]['limit'],700)
 def test_conflicting_server_ceiling_returns_409(self):
  b=self.body([]);self.s['limit']=900
  with self.assertRaises(Problem) as e:apply_plan(self.s,b)
  self.assertEqual(e.exception.status,409)
 def test_invalid_later_row_does_not_partially_save(self):
  before=copy.deepcopy(self.s);b=self.body([{'path':'new','name':'Valid','limit':200},{'path':'../escape','name':'Bad','limit':200}])
  with self.assertRaises(Problem):apply_plan(self.s,b)
  self.assertEqual(self.s,before)
 def test_sibling_overallocation_is_rejected(self):
  with self.assertRaises(Problem):apply_plan(self.s,self.body([{'path':'a','name':'A','limit':600},{'path':'b','name':'B','limit':600}]))
 def test_nested_budgets_not_double_counted(self):
  apply_plan(self.s,self.body([{'path':'a','name':'A','limit':600},{'path':'a/child','name':'Child','limit':400},{'path':'b','name':'B','limit':400}]))
  self.assertEqual(len(self.s['partitions']),3)
 def test_nested_overallocation_is_rejected(self):
  with self.assertRaises(Problem):apply_plan(self.s,self.body([{'path':'a','name':'A','limit':500},{'path':'a/child','name':'Child','limit':600}]))
 def test_below_usage_is_rejected(self):
  with self.assertRaises(Problem):apply_plan(self.s,self.body([{'path':'projects','name':'Projects','limit':99}]))
 def test_remove_budget_preserves_files(self):
  inventory=copy.deepcopy(self.s['inventory']);apply_plan(self.s,self.body([]));self.assertEqual(self.s['partitions'],[]);self.assertEqual(self.s['inventory'],inventory)
 def test_duplicate_paths_rejected(self):
  with self.assertRaises(Problem):apply_plan(self.s,self.body([{'path':'a','name':'A','limit':100},{'path':'a','name':'B','limit':100}]))
 def test_file_cannot_be_partition_folder(self):
  with self.assertRaises(Problem):apply_plan(self.s,self.body([{'path':'projects/a.txt','name':'File','limit':100}]))
 def test_physical_capacity_caps_effective_allocation(self):
  self.s['capacity']=500
  with self.assertRaises(Problem):apply_plan(self.s,self.body([{'path':'a','name':'A','limit':600}]))
 def test_empty_partition_has_no_marker_file_side_effect(self):
  before=copy.deepcopy(self.s['inventory']);apply_plan(self.s,self.body([{'path':'empty','name':'Empty','limit':900}]))
  self.assertEqual(self.s['inventory'],before)

 def test_unlimited_legacy_parent_inherits_sibling_ceiling(self):
  self.s['partitions']=[{'id':'legacy','path':'parent','name':'Parent','limit':0}]
  with self.assertRaises(Problem):apply_plan(self.s,self.body([{'path':'parent','name':'Parent','limit':0},{'path':'parent/a','name':'A','limit':600},{'path':'parent/b','name':'B','limit':600}]))
