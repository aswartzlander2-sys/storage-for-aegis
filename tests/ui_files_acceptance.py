"""Real Linux worker + real Basic/ACL/quota APIs; local CA HTTPS enrollment, not public DNS.
Start app/server.py + automatic_tls_fixture.mjs first.
Usage: python tests/ui_files_acceptance.py /absolute/disposable/robo-ui-test-runtime
"""
import base64
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import wave
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]
DATA=Path(sys.argv[1]).resolve();assert DATA.name=='robo-ui-test-runtime'
BASE='http://127.0.0.1:8800';config=json.loads((DATA/'config.json').read_text())
with sync_playwright() as p:
    admin=p.request.new_context(base_url=BASE,extra_http_headers={'X-Robo-Admin':config['admin_key'],'X-Robo-Request':'1'})
    def api(path,body=None):
        r=admin.get('/'+path) if body is None else admin.post('/'+path,data=body)
        assert r.ok,(r.status,r.text());return r.json()
    g=api('api/groups',{'name':'Robo design acceptance','sub':'ui-'+str(int(time.time()))})['group']
    password='DISPOSABLE-UI-test-password';username='design-tester'
    api('api/groups/'+g['id']+'/users',{'username':username,'password':password,'enabled':True,'rules':[{'path':'','access':'write'},{'path':'private','access':'none'},{'path':'view.txt','access':'read'}]})
    folder=DATA/('files-'+g['id']);(folder/'docs').mkdir(parents=True);(folder/'private').mkdir()
    (folder/'notes.txt').write_text('Robo Storage preview test\n')
    (folder/'docs/readme.md').write_text('# Project notes\nA real protected file.\n')
    (folder/'docs/report.csv').write_text('name,bytes\nquota,1000000000\n')
    (folder/'view.txt').write_text('Read-only document')
    (folder/'private/secret.txt').write_text('HIDDEN-SYNTHETIC-FIXTURE')
    (folder/'safe.html').write_text('<script>window.previewXss = true</script>')
    png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aZ1kAAAAASUVORK5CYII=')
    (folder/'image.png').write_bytes(png)
    with wave.open(str(folder/'sound.wav'),'wb') as audio:audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(8000);audio.writeframes(b'\0\0'*800)
    s=api('api/groups/'+g['id']+'/servers',{'kind':'linux','name':'Design test worker','path':str(folder),'limit':1_000_000_000})['server']
    command=api('api/servers/'+s['id']+'/enrollment',{})['command']
    env={**os.environ,'CURL_CA_BUNDLE':str(DATA/'cert.pem'),'SSL_CERT_FILE':str(DATA/'cert.pem')}
    run=subprocess.run(['bash','-c',command],env=env,capture_output=True,text=True,timeout=25);assert run.returncode==0,run.stderr
    other=api('api/groups/'+g['id']+'/servers',{'kind':'linux','name':'Read-only empty worker','path':str(DATA/'unused-worker')})['server']
    api('api/servers/'+other['id']+'/settings',{'name':other['name'],'readOnly':True,'limit':1_000_000_000})
    browser=p.chromium.launch();context=browser.new_context(http_credentials={'username':username,'password':password},viewport={'width':1440,'height':950},color_scheme='light')
    page=context.new_page();errors=[];outbound=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('request',lambda r:outbound.append(r.url) if not r.url.startswith((BASE,'blob:','data:')) else None)
    url=BASE+'/g/'+g['id']+'/'
    page.goto(url);expect(page.locator('#group-name')).to_have_text(g['name']);expect(page.locator('.file-card')).to_have_count(6)
    expect(page.locator('#usage')).to_contain_text('1.0 GB allocated')
    assert 'private' not in page.locator('#files').inner_text()
    assert page.locator('.drive-header').evaluate('(e)=>getComputedStyle(e).backdropFilter')!='none'
    page.screenshot(path=str(ROOT/'docs/robo-files-light-1.1.0.png'),full_page=True)
    page.get_by_role('button',name='List view',exact=True).click();expect(page.locator('#files')).to_have_class('file-list')
    page.reload();expect(page.locator('#files')).to_have_class('file-list')
    page.get_by_role('button',name='Grid view',exact=True).click()
    page.locator('[data-folder="1"]').click();expect(page.locator('.file-card')).to_have_count(2)
    expect(page.locator('#breadcrumbs')).to_contain_text('docs')
    page.locator('[data-path="docs/readme.md"]').click();expect(page.locator('#preview-content pre')).to_contain_text('A real protected file.')
    page.get_by_label('Close preview',exact=True).click();page.locator('#breadcrumbs [data-directory=""]').click()
    page.locator('[data-category=images]').click();expect(page.locator('.file-card')).to_have_count(1)
    page.locator('[data-path="image.png"]').click();expect(page.locator('#preview-content img')).to_be_visible()
    expect(page.locator('#preview-content img')).to_have_js_property('complete',True)
    assert page.locator('#preview-content img').evaluate('(e)=>e.naturalWidth')==1
    page.get_by_label('Close preview',exact=True).click()
    page.locator('[data-category=audio]').click();page.locator('[data-path="sound.wav"]').click();expect(page.locator('#preview-content audio')).to_be_visible()
    page.get_by_label('Close preview',exact=True).click();page.locator('[data-category=all]').click()
    page.locator('[data-path="safe.html"]').click();expect(page.locator('#preview-content pre')).to_contain_text('<script>');assert page.evaluate('window.previewXss') is None
    page.get_by_label('Close preview',exact=True).click();page.locator('[data-category=recent]').click();expect(page.locator('.file-card')).to_have_count(4)
    page.locator('[data-category=all]').click();page.get_by_label('Search files',exact=True).fill('report.csv');expect(page.locator('.file-card')).to_have_count(1)
    page.get_by_label('Search files',exact=True).fill('');page.locator('[data-path="view.txt"]').click();expect(page.locator('#preview-delete')).to_be_hidden()
    page.get_by_label('Close preview',exact=True).click();page.locator('#new-text').click();page.locator('#destination').fill('projects/new.txt');page.locator('#new-content').fill('Created through real UI and Linux backend.');page.locator('#confirm-file').click();expect(page.locator('#file-modal')).not_to_be_visible()
    assert (folder/'projects/new.txt').read_text()=='Created through real UI and Linux backend.'
    page.locator('#file-input').set_input_files({'name':'upload.txt','mimeType':'text/plain','buffer':b'Uploaded through browser'})
    page.locator('#confirm-file').click();expect(page.locator('#file-modal')).not_to_be_visible();assert (folder/'upload.txt').read_bytes()==b'Uploaded through browser'
    page.locator('[data-path="upload.txt"]').click();page.locator('#preview-delete').click();page.locator('#confirm-path').fill('wrong');page.locator('#confirm-file').click();expect(page.locator('#operation-error')).to_contain_text('Confirm the exact');assert (folder/'upload.txt').exists()
    page.locator('#confirm-path').fill('upload.txt');page.locator('#confirm-file').click();expect(page.locator('#file-modal')).not_to_be_visible();assert not (folder/'upload.txt').exists()
    # Server-side controls are tested directly as well as via hidden buttons.
    protected=context.request
    for target in ['view.txt','private/secret.txt']:
        response=protected.post(url+'api/upload',data={'server':s['id'],'path':target,'data':'eA=='},headers={'X-Robo-Request':'1'})
        assert response.status==403,response.text()
    used=api('api/servers/'+s['id']+'/test',{})['server']['used']
    api('api/servers/'+s['id']+'/settings',{'name':s['name'],'limit':used+2})
    page.locator('#new-text').click();page.locator('#destination').fill('over-quota.txt');page.locator('#new-content').fill('too large');page.locator('#confirm-file').click();expect(page.locator('#operation-error')).to_contain_text('quota');assert not (folder/'over-quota.txt').exists();page.locator('#cancel-file').click()
    api('api/servers/'+s['id']+'/settings',{'name':s['name'],'limit':1_000_000_000});page.locator('#refresh-files').click()
    page.get_by_label('Switch to dark theme',exact=True).click();expect(page.locator('html')).to_have_attribute('data-robo-theme','dark')
    page.screenshot(path=str(ROOT/'docs/robo-files-dark-1.1.0.png'),full_page=True)
    page.reload();expect(page.locator('html')).to_have_attribute('data-robo-theme','dark');expect(page.locator('#files .file-card').first).to_be_visible()
    page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.get_by_label('Open navigation',exact=True).click();expect(page.locator('#drive-sidebar')).to_be_visible();page.locator('[data-category=docs]').click();expect(page.locator('#drive-sidebar')).not_to_be_visible()
    page.screenshot(path=str(ROOT/'docs/robo-files-mobile-1.1.0.png'),full_page=True)
    page.locator('#storage-picker').select_option(other['id']);expect(page.locator('#files .file-card')).to_have_count(0);expect(page.locator('#upload-file')).to_be_disabled();expect(page.locator('#new-text')).to_be_disabled()
    scoped=context.new_page();scoped.goto(BASE+'/g/'+g['id']+'/s/'+s['id']+'/');expect(scoped.locator('#storage-picker option')).to_have_count(1)
    assert protected.get(BASE+'/g/'+g['id']+'/s/'+s['id']+'/api/files?server='+other['id']).status==403
    assert not errors,errors;assert not outbound,outbound
    print('REAL LOCAL HTTPS WORKER + BROWSER: grid/list persistence, folders, search, categories, recent previews, 1 GB allocation, image/audio/text previews: PASS')
    print('HTML preview rendered as inert text; no external CDN/provider requests; JavaScript errors: []')
    print('Actual UI text creation, upload, exact-path deletion confirmation, native Basic and server-side hidden/read-only ACLs + quota 507: PASS')
    print('Light/dark theme persistence, 390px mobile navigation/no overflow, read-only storage switch, server-scoped isolation: PASS')
    print('LOCAL CA fixture only; not a public/custom-domain/provider acceptance claim.')
    browser.close();admin.dispose()
