"""Real public HTTPS acceptance on an isolated actual Aegis host. Never target customer storage.
Usage: python tests/live_acceptance.py AEGIS_URL SESSION_JSON DISPOSABLE_TEST_ROOT
Uses the host's real Burrow/Cloudflare tunnel engine, not a TLS or context mock.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import urllib.error
from playwright.sync_api import sync_playwright, expect
BASE,SESSION,TEST_ROOT=sys.argv[1:]
TEST_ROOT=Path(TEST_ROOT).resolve();TEST_ROOT.mkdir(parents=True,exist_ok=True)
assert 'live-host-test' in str(TEST_ROOT), 'Only the explicitly disposable live-host-test directory is allowed'

def public(url,body=None,user=None,password=None):
    headers={'X-Robo-Request':'1'}
    if user:headers['Authorization']='Basic '+base64.b64encode((user+':'+password).encode()).decode()
    if body is not None:headers['Content-Type']='application/json'
    req=urllib.request.Request(url,data=None if body is None else json.dumps(body).encode(),headers=headers)
    for attempt in range(3):
        try:
            r=urllib.request.urlopen(req,timeout=40);break
        except urllib.error.HTTPError as e:
            r=e;break
        except (urllib.error.URLError, OSError):
            if body is not None or attempt==2:raise  # Never replay a write with an unknown outcome.
            time.sleep(.5*(attempt+1))
    return r.status,dict(r.headers),r.read()

with sync_playwright() as p:
    request=p.request.new_context(base_url=BASE,storage_state=SESSION,extra_http_headers={'X-Gate':'1','X-Robo-Request':'1'})
    def admin(path,body=None):
        url='/__gate/robo-storage/'+path
        r=request.get(url) if body is None else request.post(url,data=body,timeout=45000)
        assert r.ok,(r.status,r.text());return r.json()
    def state():return admin('api/state')
    def wait_for(predicate,description,seconds=90):
        deadline=time.time()+seconds
        while time.time()<deadline:
            value=predicate()
            if value:return value
            time.sleep(1)
        raise AssertionError(description+' timed out')
    def ready_agent():
        route=state()['agentRoute']
        return route if route['state']=='ready' else None
    route=wait_for(ready_agent,'Public enrollment HTTPS')
    status,_,body=public(route['url']+'/agent/health?probe='+'c'*32)
    assert status==200 and json.loads(body)['version']=='1.0.1'
    print('REAL PUBLIC HTTPS: Burrow-created Cloudflare enrollment route returned app identity + nonce, certificate verification enabled')
    before_ports={t['port'] for t in request.get('/__gate/api/tunnels').json()['tunnels'] if t.get('app')=='robo-storage-aegis'}
    group=admin('api/groups',{'name':'Live public acceptance','sub':'live-'+str(int(time.time())),'domain':'stale.invalid','tunnelSub':'wrong-nested','useDefaultTunnel':True})['group']
    username='live-test-user';password='DISPOSABLE-LIVE-test-password-2026'
    admin('api/groups/'+group['id']+'/users',{'username':username,'password':password,'enabled':True,'rules':[{'path':'','access':'write'},{'path':'private','access':'none'},{'path':'view.txt','access':'read'}]})
    roots=[TEST_ROOT/'linux-a',TEST_ROOT/'linux-b']
    for root in roots:root.mkdir(exist_ok=True)
    sample=b'actual public HTTPS migration checksum sample'
    (roots[0]/'sample.txt').write_bytes(sample)
    servers=[]
    for i,root in enumerate(roots):
        if i==0:
            ui_browser=p.chromium.launch();ui_context=ui_browser.new_context(storage_state=SESSION,viewport={'width':1440,'height':1000});ui=ui_context.new_page()
            ui.goto(BASE+'/__gate/robo-storage/')
            ui.locator('[data-act=add-server][data-id="'+group['id']+'"]').click()
            ui.locator('[data-kind=linux]').click()
            assert ui.locator('#modal [name=domain], #modal [name=base], #modal [name=sub], #modal [name=tunnelSub]').count()==0
            ui.locator('#modal [name=name]').fill('Live source')
            ui.locator('#linux-path').fill(str(root))
            ui.get_by_label('Generate Linux enrollment command',exact=True).click()
            ui.locator('.command').wait_for()
            command=ui.locator('.command').inner_text()
            ui.locator('#modal [name=limitValue]').fill('1')
            ui.locator('#modal [name=name]').fill('Live source edited after command')
            server=next(s for s in state()['servers'] if s['group']==group['id'] and s.get('path')==str(root))
        else:
            server=admin('api/groups/'+group['id']+'/servers',{'name':'Live destination','kind':'linux','path':str(root),'limit':1000000})['server']
            command=admin('api/servers/'+server['id']+'/enrollment',{})['command']
        assert route['url'] in command and 'localhost' not in command
        result=subprocess.run(['bash','-c',command],capture_output=True,text=True,timeout=55)
        assert result.returncode==0,('Generated public installer failed',result.returncode,result.stderr[-500:])
        servers.append(server)
        print(server['name']+': generated curl executed over real public HTTPS; write/read/delete storage probe completed')
        if i==0:
            expect(ui.locator('#linux-verification')).to_have_text('✓ Verified',timeout=30000)
            expect(ui.locator('#launch-server')).to_be_enabled()
            ui.locator('#launch-server').click()
            ui.locator('#modal').wait_for(state='hidden',timeout=45000)
            saved=next(s for s in state()['servers'] if s['id']==server['id'])
            assert saved['limit']==1_000_000_000 and saved['allocatedCapacity']==1_000_000_000,saved
            assert saved['name']=='Live source edited after command'
            assert saved['physicalCapacity']>saved['allocatedCapacity'],saved
            server=saved;servers[-1]=saved
            expect(ui.locator('.group-card').filter(has=ui.locator('[data-act=add-server][data-id="'+group['id']+'"]')).locator('.server-row').filter(has_text=saved['name']).locator('.capacity-label')).to_contain_text('of 1.0 GB')
            print('Quota regression: command generated with no limit, then edited to 1 GB; Launch saved 1,000,000,000 bytes and edited name; physical disk remains separate')
            ui.screenshot(path=str(Path(__file__).resolve().parents[1]/'docs/live-ui-server-1.0.1.png'),full_page=True)
            ui_browser.close()
            print('Actual signed-in UI: Add Server → Linux → generated public curl → live Verified → Verify & Launch succeeded, with no domain fields')
    def verified():
        ss={s['id']:s for s in state()['servers']}
        return ss if all(ss[s['id']]['verified'] and ss[s['id']]['online'] for s in servers) else None
    wait_for(verified,'Real public worker heartbeats')
    print('Two actual workers became Verified only after authenticated public HTTPS heartbeats')
    # Both attempts deliberately supply wrong server-level domains: they must be ignored.
    for server in servers:
        result=admin('api/servers/'+server['id']+'/launch',{'domain':'wrong.invalid','base':'wrong.invalid','sub':'must-not-be-used','useDefaultTunnel':False})
        assert result['inheritsGroupAddress'] is True
    def ready_group():
        g=next(g for g in state()['groups'] if g['id']==group['id'])
        return g if g['routeState']=='ready' and g['url'].startswith('https://') else None
    g=wait_for(ready_group,'Group public HTTPS identity check')
    ss={s['id']:s for s in state()['servers']}
    for server in servers:assert ss[server['id']]['url']==g['url']+'/s/'+server['id']+'/'
    tunnels=request.get('/__gate/api/tunnels').json()['tunnels']
    owned=[t for t in tunnels if t.get('app')=='robo-storage-aegis']
    assert len({t['port'] for t in owned}-before_ports)==1,[(t['port'],t['sub']) for t in owned]
    print('Default tunnel: stale nested domain ignored; one group tunnel added, shared agent tunnel, no per-server tunnels; both servers inherit group /s/ID/ addresses')
    status,headers,_=public(g['url']+'/')
    assert status==401 and 'Basic realm=' in headers.get('WWW-Authenticate','')
    assert public(g['url']+'/api/state')[0] in (401,404,403)
    print('Public group: anonymous request gets native HTTP Basic challenge; administration is not exposed')
    prefix=g['url']+'/'
    def group_call(path,body=None):return public(prefix+path,body,username,password)
    a,b=servers
    status,_,body=group_call('api/files?server='+a['id']);assert status==200
    assert json.loads(body)['files'][0]['path']=='sample.txt'
    for server in servers:
        status,_,html=public(ss[server['id']]['url'],user=username,password=password);assert status==200 and b'files.js' in html
        status,_,payload=public(ss[server['id']]['url']+'api/files',user=username,password=password)
        assert status==200 and [x['id'] for x in json.loads(payload)['servers']]==[server['id']]
    assert public(ss[a['id']]['url']+'api/files?server='+b['id'],user=username,password=password)[0]==403
    print('Actual public group and inherited per-server file-browser URLs returned 200 after Basic login')
    # A sparse file simulates near-full logical allocation without writing a gigabyte.
    near_full=roots[0]/'quota-boundary.sparse'
    with near_full.open('wb') as f:f.truncate(999_999_999-len(sample))
    try:
        boundary=admin('api/servers/'+a['id']+'/test',{})['server']
        assert boundary['used']==999_999_999 and boundary['allocatedCapacity']==1_000_000_000
        status,_,_=group_call('api/upload',{'server':a['id'],'path':'past-one-gb.txt','data':base64.b64encode(b'xx').decode()})
        assert status==507,status
        print('Real public 1 GB ceiling: 999,999,999 bytes scanned; a two-byte write returned HTTP 507; physical disk size did not expand allocation')
    finally:
        near_full.unlink(missing_ok=True)
        admin('api/servers/'+a['id']+'/test',{})
    admin('api/servers/'+b['id']+'/settings',{'limit':100,'name':b['name']})
    admin('api/servers/'+b['id']+'/partition',{'name':'Small partition','path':'small','limit':10})
    def upload(path,data):return group_call('api/upload',{'server':b['id'],'path':path,'data':base64.b64encode(data).decode()})[0]
    assert upload('private/hidden.txt',b'x')==403
    assert upload('view.txt',b'x')==403
    assert upload('small/too-big.txt',b'x'*11)==507
    assert upload('too-big.txt',b'x'*101)==507
    assert upload('small/good.txt',b'12345')==200
    assert (roots[1]/'small/good.txt').read_bytes()==b'12345'
    status,_,data=group_call('api/download?server='+b['id']+'&path=small%2Fgood.txt')
    assert status==200 and hashlib.sha256(data).digest()==hashlib.sha256(b'12345').digest()
    print('Actual public upload/download checksum matched; hidden/read-only ACLs and server/partition quotas enforced; encoded directory path works')
    browser=p.chromium.launch();ctx=browser.new_context(http_credentials={'username':username,'password':password},viewport={'width':1200,'height':800})
    page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(g['url']+'/');expect(page.locator('#group-name')).to_have_text(group['name'])
    page.screenshot(path=str(Path(__file__).resolve().parents[1]/'docs/live-public-browser.png'),full_page=True)
    assert not errors,errors;browser.close()
    print('Public HTTPS browser smoke: PASS; JavaScript errors: []')
    job=admin('api/servers/'+a['id']+'/drain',{'mode':'move','confirmName':a['name'],'targets':[{'id':b['id'],'percent':100}]})['job']
    def job_done(id):
        j=next(j for j in state()['jobs'] if j['id']==id)
        if j['state']=='error':raise AssertionError(j)
        return j if j['state']=='done' else None
    wait_for(lambda:job_done(job['id']),'Public verified migration')
    assert not (roots[0]/'sample.txt').exists() and (roots[1]/'sample.txt').read_bytes()==sample
    assert next(s for s in state()['servers'] if s['id']==a['id'])['status']=='removed'
    print('Actual public worker migration: copy → read-back checksum → source-change check → source deletion → disconnect: PASS')
    job=admin('api/servers/'+b['id']+'/drain',{'mode':'erase','confirmName':b['name']})['job']
    wait_for(lambda:job_done(job['id']),'Public explicit erasure')
    assert not (roots[1]/'sample.txt').exists() and not (roots[1]/'small/good.txt').exists()
    print('Actual public worker erasure and empty-inventory disconnect: PASS')
    print('Real IDrive E2/CloudGate accounts and custom-domain DNS: NOT TESTED; no supplied provider credentials used')
    removed=request.post('/__gate/api/x/robo-storage-aegis/unpublish',data={'key':group['id']})
    assert removed.ok
    after_ports={t['port'] for t in request.get('/__gate/api/tunnels').json()['tunnels'] if t.get('app')=='robo-storage-aegis'}
    assert after_ports==before_ports
    print('Live group cleanup removed only its owned tunnel; enrollment and other groups unchanged')
    print('LIVE PUBLIC ACCEPTANCE: PASS')
    request.dispose()
