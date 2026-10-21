import json
import sys
sys.dont_write_bytecode = True
from backends import host_call
cfg = json.load(open(sys.argv[1]))
result = host_call(cfg, 'POST', '/x/' + cfg['id'] + '/unpublish-all', {})
print('removed owned routes:', bool(result.get('ok')))
