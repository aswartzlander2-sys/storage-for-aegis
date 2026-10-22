"""1.2.0 real Aegis-host acceptance on a NEW DISPOSABLE host, never production.
Usage: python tests/host_refresh.py http://127.0.0.1:4310 /absolute/test-aegis-home
Runs install/update/uninstall and keeps the disposable addon data for inspection.
"""
import json
import os
from pathlib import Path
import sys
import time
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]
BASE,HOME=sys.argv[1:]
HOME=Path(HOME).resolve()
with sync_playwright() as p:
    browser=p.chromium.launch()
    session=HOME/'browser-session.json'
    context=browser.new_context(viewport={'width':1440,'height':1000}, **({'storage_state':str(session)} if session.exists() else {}))
    page=context.new_page();errors=[];page.on('pageerror',lambda e: errors.append(str(e)))
    if not session.exists():
        page.goto(BASE+'/__gate/setup')
        page.locator('#username').fill('local-test-admin')
        page.locator('#password').fill('DISPOSABLE-host-test-password-2026')
        page.locator('#password2').fill('DISPOSABLE-host-test-password-2026')
        page.locator('#go').click();page.wait_for_url('**/__gate/welcome')
        context.storage_state(path=str(session))
    request=context.request
    def host(path,body=None):
        r=request.get(BASE+path) if body is None else request.post(BASE+path,data=body,headers={'X-Gate':'1','X-Robo-Request':'1'})
        assert r.ok,(r.status,r.text());return r.json()
    def job(verb,body):
        j=host('/__gate/api/addons/robo-storage-aegis/'+verb,body)['job'];deadline=time.time()+45
        while time.time()<deadline:
            result=host('/__gate/api/addons/jobs/'+j['id'])
            if result['state']!='running':
                assert result['state']=='done',result
                print('Actual Aegis '+verb+': DONE')
                return result
            time.sleep(.2)
        raise AssertionError('Host job timeout')
    rec=next((a for a in host('/__gate/api/addons')['addons'] if a['id']=='robo-storage-aegis'),None)
    if rec is None: rec=host('/__gate/api/addons/add',{'source':str(ROOT)})['addon']
    assert rec['version']=='1.2.0'
    assert 'PUBLIC_URL' not in [s['key'] for s in rec['settings']]
    print('Actual Aegis add: accepted 1.2.0; no enrollment URL setting')
    job('install',{'settings':{'PORT':8799,'ADMIN_USER':'admin','ADMIN_PASSWORD':''}})
    page.goto(BASE+'/__gate/robo-storage/')
    expect(page.frame_locator('#cloud-browser').locator('h1')).to_have_text('Robo Cloud')
    page.screenshot(path=str(ROOT/'docs/actual-host-cloud-1.2.0.png'),full_page=True)
    page.goto(BASE+'/__gate/robo-storage/manage')
    expect(page.get_by_role('heading',name='Server groups',exact=True)).to_be_visible()
    assert page.locator('.sidebar').count()==0
    assert page.locator('.top .tabs a.on').inner_text()=='Robo Cloud'
    assert page.locator('body').evaluate('(el)=>getComputedStyle(el).backgroundColor')=='rgb(3, 3, 4)'
    assert page.locator('.btn.primary').first.evaluate('(el)=>getComputedStyle(el).backgroundColor')=='rgb(255, 255, 255)'
    css=request.get(BASE+'/__gate/robo-storage/assets/aegis.css');assert css.ok
    assert css.body()==(ROOT/'app/static/aegis.css').read_bytes()
    print('Actual host mount: 200; unchanged upstream Aegis navigation/CSS plus scoped Robo glass panels and white controls')
    assert request.get('http://127.0.0.1:8799/api/state').status==401
    deadline=time.time()+8
    while time.time()<deadline:
        tunnels=host('/__gate/api/tunnels')['tunnels']
        owned=[t for t in tunnels if t.get('app')=='robo-storage-aegis' and t.get('sub','').startswith('robo-agent-')]
        if owned: break
        time.sleep(.1)
    assert len(owned)==1,owned
    t=owned[0];assert t['sub'].startswith('robo-agent-');assert t['access']=='public'
    print('Actual Burrow automatically created one addon-owned agent route; no manual tunnel or URL supplied')
    for path in ['/','/api/state','/__gate/robo-storage/']:
        assert request.get('http://127.0.0.1:'+str(t['targetPort'])+path).status==404
    nonce='b'*32
    r=request.get('http://127.0.0.1:'+str(t['targetPort'])+'/agent/health?probe='+nonce)
    assert r.ok and r.json()['probe']==nonce
    print('Actual agent-only proxy: health reaches service; dashboard/admin paths 404; direct admin 401')
    def admin(path,body=None):return host('/__gate/robo-storage/'+path,body)
    group=next((g for g in admin('api/state')['groups'] if g['sub']=='acceptance'),None)
    if not group: group=admin('api/groups',{'name':'Host acceptance','sub':'acceptance','domain':''})['group']
    server=admin('api/groups/'+group['id']+'/servers',{'name':'Unverified worker','kind':'linux','path':'~/robo-host-test'})['server']
    username='file-smoke-'+str(int(time.time()))
    admin('api/groups/'+group['id']+'/users',{'username':username,'password':'DISPOSABLE-file-test-password','enabled':True,'rules':[{'path':'','access':'write'}]})
    files=browser.new_context(http_credentials={'username':username,'password':'DISPOSABLE-file-test-password'},viewport={'width':1200,'height':800})
    filepage=files.new_page();filepage.on('pageerror',lambda e:errors.append(str(e)))
    filepage.goto('http://127.0.0.1:8799/g/'+group['id']+'/')
    expect(filepage.locator('h1')).to_have_text('Robo Cloud')
    expect(filepage.locator('#cloudStoragePicker option').first).to_be_attached()
    assert filepage.locator('header.glass').is_visible()
    assert filepage.locator('#sidebarAside').is_visible()
    filepage.screenshot(path=str(ROOT/'docs/actual-host-files-1.2.0.png'),full_page=True)
    filepage.set_viewport_size({'width':390,'height':844})
    assert filepage.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    files.close();print('File browser: native Basic login, Robo glass header/sidebar, server selector and mobile width checked')
    state=admin('api/state');assert state['agentRoute']['state'] in ('pending','error','ready')
    r=request.post(BASE+'/__gate/robo-storage/api/servers/'+server['id']+'/enrollment',data={},headers={'X-Robo-Request':'1'})
    if not r.ok:
        assert r.status==503,(r.status,r.text())
        assert 'command' not in r.json() and 'Set Agent enrollment' not in r.text()
        print('No verified public HTTPS route in this sandbox: command safely blocked with automatic-provisioning status (503)')
    else:
        assert r.ok;print('Public HTTPS route passed its health check; command generation available')
    page.locator('[data-nav=connections]').click()
    expect(page.get_by_role('heading',name='Agent enrollment address')).to_be_visible()
    page.screenshot(path=str(ROOT/'docs/actual-host-connections-1.2.0.png'),full_page=True)
    before_port=t['port'];job('update',{})
    page.goto(BASE+'/__gate/robo-storage/manage');expect(page.get_by_role('heading',name='Server groups',exact=True)).to_be_visible()
    owned=[t for t in host('/__gate/api/tunnels')['tunnels'] if t.get('app')=='robo-storage-aegis' and t.get('sub','').startswith('robo-agent-')]
    assert len(owned)==1 and owned[0]['port']==before_port,owned
    assert any(g['id']==group['id'] for g in admin('api/state')['groups'])
    print('Actual host update: group data retained; same agent tunnel identity, no duplicate')
    page.screenshot(path=str(ROOT/'docs/actual-host-dashboard-1.2.0.png'),full_page=True)
    print('Browser page errors:',errors);assert not errors
    print('Real E2/CloudGate/live public DNS acceptance: NOT RUN')
    if os.environ.get('ROBO_KEEP_HOST_INSTALLED')!='1':
        job('uninstall',{'keep_data':True})
        assert not [t for t in host('/__gate/api/tunnels')['tunnels'] if t.get('app')=='robo-storage-aegis']
        print('Actual host uninstall: owned automatic route removed; no route recreated')
    browser.close()
