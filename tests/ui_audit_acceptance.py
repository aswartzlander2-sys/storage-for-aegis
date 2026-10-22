"""Deterministic UI race/destructive-flow audit against disposable real Linux storage.
Run after cloud_ui_acceptance.py. Network holds only reorder real API responses.
"""
import base64,json,sys
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];DATA=Path(sys.argv[1]).resolve();assert DATA.name=='cloud-test-runtime'
config=json.loads((DATA/'config.json').read_text());BASE='http://127.0.0.1:8800'
with sync_playwright() as p:
 b=p.chromium.launch();admin=b.new_context(extra_http_headers={'X-Robo-Admin':config['admin_key'],'X-Robo-Request':'1'})
 def api(path,body=None):
  r=admin.request.get(BASE+'/'+path) if body is None else admin.request.post(BASE+'/'+path,data=body)
  assert r.ok,(r.status,r.text());return r.json()
 state=api('api/state');g=state['groups'][-1];s=next(s for s in state['servers'] if s['group']==g['id'] and s['name']=='Design test worker');sid=s['id'];folder=Path(s['path'])
 for name,text in {'race/a.txt':'alpha-content','other/b.txt':'beta-content','context-folder/one.txt':'one','context-folder/nested/two.txt':'two'}.items():
  file=folder/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text(text)
 api('api/servers/'+sid+'/test',{})
 # Create-only conflict checks use the real backend and preserve bytes.
 r=admin.request.post(BASE+'/api/cloud/upload',data={'server':sid,'path':'other/b.txt','data':base64.b64encode(b'').decode(),'createOnly':True});assert r.status==409,r.text();assert (folder/'other/b.txt').read_text()=='beta-content'
 ctx=b.new_context(http_credentials={'username':'design-tester','password':'DISPOSABLE-UI-test-password'},viewport={'width':1440,'height':1000});page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d:d.accept());page.goto(BASE+'/g/'+g['id']+'/');expect(page.locator('#fileGrid h4',has_text='race')).to_be_visible()
 held=[]
 def hold_first(route):
  if not held:held.append(route)
  else:route.continue_()
 page.route('**/api/files?*',hold_first)
 with page.expect_request('**/api/files?*'):page.evaluate("()=>{currentPath='race/';loadDirectory()}")
 page.evaluate("()=>{currentPath='other/';loadDirectory()}")
 expect(page.locator('#fileGrid h4',has_text='b.txt')).to_be_visible();assert len(held)==1;held[0].continue_();page.wait_for_function('()=>cloudBusy===0');expect(page.locator('#fileGrid h4',has_text='b.txt')).to_be_visible();expect(page.locator('#fileGrid h4',has_text='a.txt')).to_have_count(0)
 page.unroute('**/api/files?*',hold_first);print('Out-of-order directory responses do not replace the current folder: PASS')
 # An old download completing after a newer preview cannot poison cache/editor identity.
 downloads=[]
 def hold_alpha(route):
  key=parse_qs(urlsplit(route.request.url).query).get('path',[''])[0]
  if key=='race/a.txt' and not downloads:downloads.append(route)
  else:route.continue_()
 page.route('**/api/download?*',hold_alpha)
 with page.expect_request(lambda r:'download?' in r.url and 'a.txt' in r.url):page.evaluate("()=>{openFilePreview({name:'a.txt',key:'race/a.txt',size:13,category:'code'})}")
 page.evaluate("()=>{openFilePreview({name:'b.txt',key:'other/b.txt',size:12,category:'code'})}")
 page.wait_for_function("()=>expandedCodeEditor&&expandedCodeEditor.getValue()==='beta-content'")
 assert len(downloads)==1
 with page.expect_response(lambda r:'download?' in r.url and 'a.txt' in r.url) as old_response:downloads[0].continue_()
 old_response.value.body();page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(resolve))');assert page.evaluate('expandedCodeEditor.getValue()')=='beta-content';assert page.evaluate('cachedCodeKey')=='other/b.txt'
 page.unroute('**/api/download?*',hold_alpha);print('Out-of-order preview fetch cannot change the new file or cache: PASS')
 # Edit during a pending save: persisted snapshot succeeds, newer local edits stay dirty.
 saves=[]
 def hold_save(route):saves.append(route)
 page.route('**/api/upload',hold_save);page.locator('#expandedCodeModeBtn').click();page.evaluate("expandedCodeEditor.setValue('saved-snapshot',-1)")
 with page.expect_request('**/api/upload'):page.locator('#expandedSaveCodeBtn').click()
 page.evaluate("expandedCodeEditor.setValue('newer-unsaved-edits',-1)");expect(page.locator('#expandedSaveCodeBtn')).to_be_disabled();assert len(saves)==1
 with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/api/upload'),timeout=45000):saves[0].continue_()
 expect(page.locator('#expandedSaveCodeBtn')).to_be_enabled();assert page.evaluate('expandedCodeEditorDirty');assert page.evaluate('expandedCodeEditor.getValue()')=='newer-unsaved-edits';assert (folder/'other/b.txt').read_text()=='saved-snapshot'
 page.unroute('**/api/upload',hold_save);page.locator('#closeExpandedPreviewBtn').click();print('Save-in-flight keeps newer edits dirty and blocks duplicate saves: PASS')
 page.evaluate("()=>{currentPath='';loadDirectory()}");card=page.locator('#fileGrid>[data-cloud-key="context-folder/"]');expect(card).to_be_visible();card.click(button='right');page.locator('[data-ctx=delete]').click();expect(page.locator('#deleteModal')).to_be_visible();page.locator('#confirmDeleteBtn').click();expect(card).to_have_count(0,timeout=45000);assert not (folder/'context-folder/one.txt').exists();assert not (folder/'context-folder/nested/two.txt').exists();print('Context-menu folder delete removes confirmed descendants, not a no-op marker: PASS')
 # Switching sources drops transient state, stale selection and editor/cache identity.
 page.evaluate("midiSongCache.set('same-name.mid',{stale:true})");source=page.locator('#cloudStoragePicker');other=next(x for x in state['servers'] if x['group']==g['id'] and x['id']!=sid);source.select_option(other['id']);page.wait_for_function('()=>cloudBusy===0');assert page.evaluate("cachedCodeKey===''&&selectedItem===null&&selectedItems.size===0&&allS3Items.length===0&&midiSongCache.size===0");source.select_option(sid);expect(page.locator('#fileGrid h4',has_text='race')).to_be_visible()
 values=page.evaluate("""()=>{const quota=STORAGE_QUOTA_BYTES,bar=document.createElement('div');bar.style.cssText='width:1000px;height:8px;display:flex';document.body.appendChild(bar);try{STORAGE_QUOTA_BYTES=0;paintStorageBar({bar},{other:10},10);const unknown=[...bar.querySelectorAll('.storage-seg')].map(x=>x.style.width);STORAGE_QUOTA_BYTES=100;paintStorageBar({bar},{audio:25},75);const known=[...bar.querySelectorAll('.storage-seg')].map(x=>x.style.width);return {unknown,known}}finally{STORAGE_QUOTA_BYTES=quota;bar.remove()}}""")
 assert values=={'unknown':['0%'],'known':['25%','50%']},values;print('Explorer unknown capacity has no invented fraction; hidden/unlisted usage fills the correct remaining used share: PASS')
 assert not errors,errors;page.screenshot(path=str(ROOT/'docs/explorer-audit-1.3.0.png'),full_page=True);print('Storage switch/reset, original controls and JavaScript errors []: PASS')
 ctx.close();admin.close();b.close()
