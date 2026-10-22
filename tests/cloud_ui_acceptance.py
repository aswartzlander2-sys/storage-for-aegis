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
DATA=Path(sys.argv[1]).resolve();assert DATA.name=='cloud-test-runtime'
BASE='http://127.0.0.1:8800';config=json.loads((DATA/'config.json').read_text())
with sync_playwright() as p:
    admin=p.request.new_context(base_url=BASE,extra_http_headers={'X-Robo-Admin':config['admin_key'],'X-Robo-Request':'1'})
    def api(path,body=None):
        r=admin.get('/'+path) if body is None else admin.post('/'+path,data=body)
        assert r.ok,(r.status,r.text());return r.json()
    g=api('api/groups',{'name':'Robo Cloud acceptance','sub':'ui-'+str(int(time.time()))})['group']
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
    page=context.new_page();errors=[];external=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('request',lambda r:external.append(r.url) if not r.url.startswith((BASE,'blob:','data:')) else None)
    url=BASE+'/g/'+g['id']+'/'
    page.goto(url);expect(page.locator('#fileGrid > div')).to_have_count(6)
    expect(page.locator('h1')).to_have_text('Robo Cloud');expect(page.locator('#storageQuotaText')).to_have_text('1 GB')
    assert not page.locator('#openSidebarBtn').is_visible()
    assert 'private' not in page.locator('#fileGrid').inner_text()
    page.screenshot(path=str(ROOT/'docs/cloud-original-light-1.2.0.png'),full_page=True)
    def card(name):return page.locator('#fileGrid > div').filter(has=page.locator('h4',has_text=name))
    card('notes.txt').click();expect(page.locator('#expandedCodeEditorContainer.ace_editor')).to_be_visible()
    page.locator('#expandedCodeModeBtn').click();page.evaluate("() => expandedCodeEditor.setValue('Edited through original Ace editor', -1)")
    with page.expect_response(lambda r:r.request.method=='POST' and '/api/upload' in r.url) as saved:page.locator('#expandedSaveCodeBtn').click()
    assert saved.value.ok,saved.value.text()
    expect(page.locator('#expandedSaveCodeBtn')).to_be_disabled()
    assert (folder/'notes.txt').read_text()=='Edited through original Ace editor'
    page.locator('#closeExpandedPreviewBtn').click()
    card('image.png').click();expect(page.locator('#expandedPreviewContent img')).to_be_visible();page.locator('#closeExpandedPreviewBtn').click()
    card('safe.html').click();expect(page.locator('#expandedCodeEditorContainer')).to_be_visible();page.locator('#expandedCodeModeBtn').click();page.locator('#expandedToggleHtmlRender').click();expect(page.locator('#expandedHtmlRenderIframe')).to_be_visible()
    assert page.locator('#expandedHtmlRenderIframe').get_attribute('sandbox')==''
    assert page.evaluate('window.previewXss') is None
    page.locator('#closeExpandedPreviewBtn').click()
    card('docs').click();expect(page.locator('#fileGrid > div')).to_have_count(2)
    page.locator('#breadcrumbContainer button').first.click();expect(page.locator('#fileGrid > div')).to_have_count(6)
    card('notes.txt').hover();card('notes.txt').locator('[data-rename-btn]').click();page.locator('#renameInput').fill('renamed.txt');page.locator('#confirmRenameBtn').click();expect(page.locator('#renameModal')).to_have_class(__import__('re').compile('hidden'))
    assert (folder/'renamed.txt').read_text()=='Edited through original Ace editor' and not (folder/'notes.txt').exists()
    page.locator('#openNewFolderModalBtn').click();page.locator('#newFolderNameInput').fill('new-folder');page.locator('#confirmNewFolderBtn').click();expect(card('new-folder')).to_be_visible();assert (folder/'new-folder/.keep').exists()
    page.locator('#sidebarNewBtn').click();page.locator('[data-new-action=file]').click();page.locator('#newFileNameInput').fill('new.txt');page.locator('#createAndEditFileBtn').click();expect(page.locator('#expandedCodeEditorContainer')).to_be_visible();page.locator('#closeExpandedPreviewBtn').click();assert (folder/'new.txt').exists()
    page.locator('#fileInput').set_input_files({'name':'upload.txt','mimeType':'text/plain','buffer':b'Original upload control'})
    expect(card('upload.txt')).to_be_visible();assert (folder/'upload.txt').read_bytes()==b'Original upload control'
    card('upload.txt').click();page.locator('#expandedInfoBtn').click();page.locator('#deleteFileBtn').click();page.locator('#confirmDeleteBtn').click();expect(card('upload.txt')).to_have_count(0);assert not (folder/'upload.txt').exists()
    dangerous='<img src=x onerror=alert(1)>.txt'
    page.locator('#fileInput').set_input_files({'name':dangerous,'mimeType':'text/plain','buffer':b'Literal filename'})
    expect(card(dangerous)).to_be_visible();assert card(dangerous).locator('img').count()==0
    page.locator('#selectToggleBtn').click()
    for name in ['new.txt','new-folder',dangerous]:card(name).click()
    page.locator('#deleteSelectedBtn').click()
    with page.expect_response(lambda r:r.request.method=='POST' and '/api/delete' in r.url):page.locator('#confirmDeleteBtn').click()
    expect(card('new.txt')).to_have_count(0)
    assert not (folder/'new.txt').exists() and not (folder/'new-folder/.keep').exists() and not (folder/dangerous).exists()
    page.locator('#cloudStoragePicker').select_option(other['id']);expect(page.locator('#openNewFolderModalBtn')).to_be_disabled()
    page.locator('#cloudStoragePicker').select_option(s['id']);expect(card('renamed.txt')).to_be_visible()
    card('view.txt').click();expect(page.locator('#expandedCodeEditorContainer')).to_be_visible();expect(page.locator('#expandedCodeModeBtn')).to_be_disabled();page.locator('#closeExpandedPreviewBtn').click()
    page.locator('#viewListBtn').click();expect(page.locator('#fileList')).to_be_visible();page.locator('#viewGridBtn').click()
    for target in ['view.txt','private/secret.txt']:
        response=context.request.post(url+'api/upload',data={'server':s['id'],'path':target,'data':'eA=='},headers={'X-Robo-Request':'1'});assert response.status==403
    # Protected admin routes are not opened by a group Basic login.
    assert context.request.get(BASE+'/api/cloud/files').status==401
    response=context.request.get(url+'api/download?server='+s['id']+'&path=renamed.txt&inline=1',headers={'Range':'bytes=0-5'});assert response.status==206 and response.body()==b'Edited'
    used=api('api/servers/'+s['id']+'/test',{})['server']['used'];api('api/servers/'+s['id']+'/settings',{'name':s['name'],'limit':used})
    response=context.request.post(url+'api/upload',data={'server':s['id'],'path':'over.txt','data':'eA=='},headers={'X-Robo-Request':'1'});assert response.status==507
    api('api/servers/'+s['id']+'/settings',{'name':s['name'],'limit':1_000_000_000})
    page.emulate_media(color_scheme='dark');page.screenshot(path=str(ROOT/'docs/cloud-original-dark-1.2.0.png'),full_page=True)
    page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.locator('#openSidebarBtn').click();expect(page.locator('#sidebarAside')).to_be_visible();page.locator('[data-cat=image]').click()
    page.screenshot(path=str(ROOT/'docs/cloud-original-mobile-1.2.0.png'),full_page=True)
    # Actual administrative landing uses the same document, not the rejected replacement.
    admin_context=browser.new_context(extra_http_headers={'X-Robo-Admin':config['admin_key']},viewport={'width':1440,'height':950});a=admin_context.new_page();a.goto(BASE+'/');frame=a.frame_locator('#cloud-browser')
    expect(frame.locator('#cloudStoragePicker option')).to_have_count(sum(v['status']!='removed' for v in api('api/state')['servers']));frame.locator('#cloudStoragePicker').select_option(s['id']);expect(frame.locator('h1')).to_have_text('Robo Cloud');expect(frame.locator('#fileGrid h4',has_text='renamed.txt')).to_be_visible()
    a.screenshot(path=str(ROOT/'docs/cloud-aegis-shell-1.2.0.png'),full_page=True)
    assert not errors,errors;assert not external,external
    print('ACTUAL SUPPLIED UI + REAL LINUX WORKER: original grid/list, folder navigation, thumbnail/preview, Ace edit/save, HTML Render sandbox, rename, new folder, new file, upload, confirmed single/bulk delete, zero-byte folder marker, filename HTML escaping and read-only controls: PASS')
    print('Basic/ACL/server isolation, admin separation, 1 GB allocation, quota 507 and media byte range 206: PASS')
    print('Original light/dark/mobile layout, Aegis shell and same original admin browser; no external provider/CDN requests; JS errors: []')
    print('Local CA HTTPS fixture, not a public/provider/custom-domain acceptance claim.')
    browser.close();admin.dispose()
