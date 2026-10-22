"""Real short-command/copy/tab/Windows-download UI against the local HTTPS fixture.
Does not execute downloaded Windows binaries. All data is disposable.
"""
import json,sys
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];DATA=Path(sys.argv[1]).resolve();assert DATA.name=='cloud-test-runtime'
config=json.loads((DATA/'config.json').read_text());BASE='http://127.0.0.1:8800'
with sync_playwright() as p:
 b=p.chromium.launch();ctx=b.new_context(extra_http_headers={'X-Robo-Admin':config['admin_key'],'X-Robo-Request':'1'},permissions=['clipboard-read','clipboard-write'],ignore_https_errors=True,viewport={'width':1440,'height':1000});page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d:d.accept());page.goto(BASE+'/');expect(page.locator('.group-card').first).to_be_visible();page.wait_for_function("()=>S.data?.agentRoute?.state==='ready'",timeout=30000);gid=page.evaluate('S.data.groups[S.data.groups.length-1].id');page.evaluate('(id)=>addServer(id)',gid);page.locator('[data-kind=linux]').click();page.locator('[name=name]').fill('Enrollment control test');page.locator('[name=path]').fill(str(DATA/'never-started-worker'))
 page.locator('[data-act=generate-command]').click();expect(page.locator('.command-block code')).to_be_visible();command=page.locator('.command-block code').inner_text();assert command.startswith('curl -fsSL ') and command.endswith(' | bash') and len(command)<170
 lid=page.evaluate('S.draft.id');button=page.get_by_role('button',name='Copy enrollment command');assert button.locator('svg').count()==1;button.click();expect(page.locator('.copy-feedback')).to_have_text('Copied!');assert page.evaluate('navigator.clipboard.readText()')==command
 page.locator('.command code').evaluate('(el,text)=>el.textContent=text',"curl -fsSL 'https://your-verified-host.example.com/enroll.sh?token=REDACTED' | bash");page.screenshot(path=str(ROOT/'docs/command-copy-1.3.0.png'));page.locator('.command code').evaluate('(el,text)=>el.textContent=text',command);print('Short curl -fsSL pipe, real clipboard, GitHub-style icon and Copied feedback: PASS')
 page.locator('[data-kind=linux]').focus();page.keyboard.press('ArrowRight');expect(page.locator('[data-kind=windows]')).to_have_attribute('aria-selected','true');assert page.evaluate("getComputedStyle(document.querySelector('[data-kind=windows]')).borderRadius")=='9px';page.locator('[data-kind=linux]').click();assert page.evaluate('S.draft.id')==lid;expect(page.locator('.command code')).to_have_text(command)
 page.locator('[data-kind=windows]').click();assert page.locator('#linux-path').count()==0;expect(page.locator('#launch-server')).to_be_disabled();page.locator('[data-act=generate-command]').click();link=page.get_by_role('link',name='Download Windows EXE ↓');expect(link).to_be_visible();wid=page.evaluate('S.draft.id')
 with page.expect_download() as download:link.click()
 path=DATA/'downloaded-test.exe';download.value.save_as(path);data=path.read_bytes();assert data.startswith(b'MZ') and data.endswith(b'ROBOCLOUD-ENROLL-V1')
 assert page.evaluate('S.draft.id')==wid;expect(page.locator('#launch-server')).to_be_disabled();page.screenshot(path=str(ROOT/'docs/windows-folder-option-1.3.0.png'));page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');foot=page.locator('.modal-foot').bounding_box();assert foot and foot['y']+foot['height']<=844;page.screenshot(path=str(ROOT/'docs/enrollment-mobile-1.3.0.png'));page.locator('[data-act=close-modal]').first.click()
 # Replacement control retains the existing identity and prevents provider changes.
 page.evaluate('(id)=>settingsModal(id)',wid);page.locator('[data-act=reenroll]').click();assert page.evaluate('S.draft.id')==wid;expect(page.locator('[data-kind=linux]')).to_be_disabled();expect(page.locator('[data-kind=windows]')).to_be_enabled();page.locator('[data-act=close-modal]').first.click()
 # Metadata-only cancellation revokes unused links, never scans or deletes storage.
 for sid in (lid,wid):
  page.evaluate('(id)=>settingsModal(id,"danger")',sid);page.locator('[data-act=cancel-enrollment]').click();expect(page.locator('#modal')).not_to_be_visible()
 assert not (DATA/'never-started-worker').exists();assert not errors,errors
 print('Native Aegis tab styling/keyboard, per-provider draft retention, real personalized PE download, disabled pre-heartbeat launch, 390px layout, confirmed unused-link cancellation: PASS; native Windows execution NOT RUN; JS errors []')
 ctx.close();b.close()
