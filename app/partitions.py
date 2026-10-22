"""Atomic, optimistic logical-budget plans. Never format, move or erase files."""
from core import require,clean_path,label,quota,uid,validate_partitions,capacity_view

def apply_plan(server,body):
    require(body.get('confirm') is True,'Review and confirm the partition plan.')
    old=server.get('partitions',[])
    require(body.get('expectedLimit')==server['limit'] and body.get('expected')==old,'Storage settings changed. Reload before applying your plan.',409)
    rows=body.get('partitions');require(type(rows) is list and len(rows)<=256,'Use a list of at most 256 logical partitions.')
    proposed=[];seen=set();by_path={p['path']:p for p in old}
    for row in rows:
        require(type(row) is dict,'Invalid partition entry.')
        path=clean_path(row.get('path',''),False);require(path not in seen,'Duplicate partition directory.');seen.add(path)
        limit=quota(row.get('limit',0));existing=by_path.get(path)
        require(limit>0 or (existing and existing['limit']==0),'New partitions need a positive budget.')
        require(not any(path==f['path'] or path.startswith(f['path']+'/') for f in server['inventory']),'A file occupies the partition directory.')
        used=sum(f['size'] for f in server['inventory'] if f['path'].startswith(path+'/'))
        require(not limit or limit>=used,'Partition quota is below current usage.')
        proposed.append({'id':existing['id'] if existing else uid(),'name':label(row.get('name',path)),'path':path,'limit':limit})
    validate_partitions(proposed,capacity_view(server)['allocatedCapacity'] or server['limit'])
    server['partitions']=proposed
    return proposed
