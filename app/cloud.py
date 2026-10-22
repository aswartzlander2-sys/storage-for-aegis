"""Robo Cloud gateway support. Keeps the supplied browser independent of provider keys."""
import hashlib
from core import require, clean_path, visible, MAX_FILE, capacity_view
from backends import backend

# Trusted application scripts are local. Uploaded HTML renders in an empty sandbox.
CLOUD_CSP = "default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; frame-src 'self' blob:; worker-src 'self' blob:; font-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'wasm-unsafe-eval'; connect-src 'self' blob:; object-src 'none'; base-uri 'self'; form-action 'self'"

def visible_partitions(server,user):
    return [{'path':p['path'],'name':p['name'],'limit':p['limit']} for p in server.get('partitions',[]) if visible(user,p['path'])]

def file_view(store, servers, selected, user, group_name):
    server=next((s for s in servers if s['id']==selected),None)
    return {'partitions':visible_partitions(server,user) if server else [],'group':group_name,'username':user['username'],'servers':[{'id':s['id'],'name':s['name'],'groupName':store.get('groups',s['group'])['name'],'status':s['status'],'used':s['used'],'limit':s['limit'],'readOnly':s.get('readOnly',False),**capacity_view(s)} for s in servers], 'selected':selected,'files':[f for f in server['inventory'] if visible(user,f['path'])] if server else [],'rules':user['rules']}

def rename(store,broker,locks,scan,upload,server,user,body):
    folder=body.get('folder',False);require(type(folder) is bool,'Invalid folder option.')
    old=clean_path(body.get('path','').rstrip('/'),False);new=clean_path(body.get('newPath','').rstrip('/'),False)
    require(old!=new and not new.startswith(old+'/'),'Choose a different destination.')
    require(server['status'] not in ('draining','removed') and not server.get('readOnly'),'Server is read-only or draining.',409)
    with locks[server['id']]:
        require(not folder or not any(p['path']==old or p['path'].startswith(old+'/') for p in server.get('partitions',[])), 'A registered partition folder cannot be renamed. Change its budget in the partition manager; files were not changed.',409)
        scan(server)
        sources=[f for f in server['inventory'] if f['path']==old or (folder and f['path'].startswith(old+'/'))]
        require(sources,'Source not found.',404)
        require(not any(f['path']==new or (folder and f['path'].startswith(new+'/')) for f in server['inventory']),'Destination already exists.',409)
        pairs=[(f['path'],new+f['path'][len(old):],f['size']) for f in sources]
        require(all(visible(user,a,'write') and visible(user,b,'write') for a,b,_ in pairs),'One or more paths cannot be renamed with your permissions.',403)
        require(all(size<=MAX_FILE for _,_,size in pairs),'Rename supports files up to 16 MiB; source was retained.',413)
        b=backend(server,broker);copies=[]
        # Existing quotas remain enforced; insufficient temporary copy space fails safely.
        for src,dest,_ in pairs:
            content=b.read(src);checksum=hashlib.sha256(content).digest()
            upload(server,dest,content);copies.append((src,dest,checksum))
        for src,dest,checksum in copies:
            require(hashlib.sha256(b.read(src)).digest()==checksum and hashlib.sha256(b.read(dest)).digest()==checksum,'A file changed during rename; sources were retained.',409)
        for src,dest,checksum in copies:
            require(hashlib.sha256(b.read(src)).digest()==checksum,'A source changed; remaining sources were retained.',409)
            b.delete(src)
        scan(server);store.event('Files renamed',server['name']+': '+old+' → '+new)
    return {'ok':True}
