"""Disposable real-HTTP/Chromium setup-removal acceptance (no provider accounts).
Run: PYTHONPATH=tests python tests/ui_unverified_removal.py
Requires optional Playwright + Chromium; production host needs neither.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from test_unverified_removal import UnverifiedRemovalTests

ROOT=Path(__file__).resolve().parents[1]
Fixture=UnverifiedRemovalTests
Fixture.setUpClass()
try:
    with sync_playwright() as p:
        browser=p.chromium.launch()
        try:
            ctx=browser.new_context(extra_http_headers={'X-Robo-Admin':'TEST-REMOVAL-ADMIN','X-Robo-Request':'1'},viewport={'width':1440,'height':1050})
            page=ctx.new_page();errors=[];requests=[]
            page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:requests.append(r.url));page.on('dialog',lambda d:d.accept())
            page.goto(Fixture.base+'/');page.locator('[data-act=open-group]').first.click()
            tux=page.locator('#content img[alt=Linux]').first;expect(tux).to_be_visible();assert tux.evaluate('(img)=>img.complete&&img.naturalWidth>0')
            print('Original locally embedded Tux renders in Linux server rows: PASS')
            for kind in ('linux','e2','cloudgate','windows'):
                id=Fixture.legacy[kind]
                page.locator(f'[data-act=server-settings][data-id="{id}"]').click();page.locator('[data-act=settings-tab][data-tab=danger]').click()
                page.locator('[data-act=remove-unverified-dialog]').click();expect(page.locator('#modal')).to_be_visible()
                page.locator('[data-act=disconnect-unverified]').click();expect(page.locator('#modal-error')).to_contain_text('Acknowledge')
                page.locator('[name=keepRemoteFiles]').check();page.locator('[name=confirmName]').fill('wrong');page.locator('[data-act=disconnect-unverified]').click();expect(page.locator('#modal-error')).to_contain_text('exact server name')
                page.locator('[name=confirmName]').fill('Legacy '+kind)
                if kind=='linux':
                    page.locator('[data-act=close-modal]').first.click();page.locator(f'[data-act=server-settings][data-id="{id}"]').click();page.locator('[data-act=settings-tab][data-tab=danger]').click();page.locator('[data-act=remove-unverified-dialog]').click();page.locator('[name=confirmName]').fill('Legacy linux');page.locator('[name=keepRemoteFiles]').check()
                    page.screenshot(path=str(ROOT/'docs/unverified-removal-1.3.2.jpg'),quality=65)
                    page.set_viewport_size({'width':390,'height':844});assert page.evaluate('()=>document.documentElement.scrollWidth<=innerWidth')
                    footer=page.locator('.modal-foot').bounding_box();assert footer and footer['y']+footer['height']<=844,footer
                    page.screenshot(path=str(ROOT/'docs/unverified-removal-mobile-1.3.2.jpg'),quality=65)
                page.locator('[data-act=disconnect-unverified]').click();expect(page.locator('#modal')).not_to_be_visible();expect(page.locator(f'[data-act=server-settings][data-id="{id}"]')).to_have_count(0)
                page.set_viewport_size({'width':1440,'height':1050})
            print('All four unverified providers already draining: exact-name/keep-files checks, removal from UI, no remote operations: PASS')
            id=Fixture.unused['id'];page.locator(f'[data-act=server-settings][data-id="{id}"]').click();page.locator('[data-act=settings-tab][data-tab=danger]').click();page.locator('[data-act=cancel-enrollment]').click();expect(page.locator('#modal')).not_to_be_visible();expect(page.locator(f'[data-act=server-settings][data-id="{id}"]')).to_have_count(0)
            print('Old unenrolled + stuck-draining Cancel enrollment path: PASS')
            page.locator('[data-act=add-server]').first.click();page.locator('[data-kind=linux]').click();image=page.locator('[data-kind=linux] img');assert image.evaluate('(img)=>img.complete&&img.naturalWidth>0');page.locator('[data-act=close-modal]').first.click()
            print('Original Tux renders in Linux setup tab; 390px confirmation footer remains reachable: PASS')
            case=Fixture('test_original_tux_is_self_contained_and_attributed');verified=case.create();token=case.installer(verified)
            status,enrolled=case.call('/agent/enroll',{'platform':'linux','root':'/tmp/robo-test','files':[{'path':'keep.txt','size':9}],'capacity':512000},auth=False,token=token);assert status==200
            assert case.call('/agent/poll',{},auth=False,token=enrolled['token'])[0]==200
            page.goto(Fixture.base+'/');page.locator(f'[data-act=open-group][data-id="{verified["group"]}"]').click();page.locator(f'[data-act=server-settings][data-id="{verified["id"]}"]').click();page.locator('[data-act=settings-tab][data-tab=danger]').click();page.locator('[data-act=remove-dialog]').click();expect(page.locator('#move-files')).to_be_visible();page.locator('#move-files').uncheck();page.locator('[data-act=confirm-remove]').click();expect(page.locator('[data-act=erase-now]')).to_be_visible();expect(page.locator('[name=understand]')).to_be_visible();expect(page.locator('[data-act=disconnect-unverified]')).to_have_count(0);page.locator('[data-act=close-modal]').first.click()
            print('Verified server still uses Move/Erase with the separate destructive confirmation; no shortcut: PASS')
            unsafe=case.create('cloudgate');name='Worker <img src=x onerror="window.BAD=true"> & test';assert case.call('/api/servers/'+unsafe['id']+'/settings',{'name':name})[0]==200
            page.goto(Fixture.base+'/');page.locator(f'[data-act=open-group][data-id="{unsafe["group"]}"]').click();page.locator(f'[data-act=server-settings][data-id="{unsafe["id"]}"]').click();page.locator('[data-act=settings-tab][data-tab=danger]').click();page.locator('[data-act=remove-unverified-dialog]').click();expect(page.locator('#modal label img')).to_have_count(0);expect(page.get_by_text('Type “'+name+'” to confirm',exact=True)).to_be_visible();assert page.evaluate('()=>window.BAD===undefined');page.locator('[data-act=close-modal]').first.click()
            print('Untrusted server name remains escaped text in the new confirmation: PASS')
            assert (Fixture.keep/'keep.txt').read_text()=='keep data'
            assert all(url.startswith(Fixture.base+'/') for url in requests),[url for url in requests if not url.startswith(Fixture.base+'/')]
            assert not errors,errors
            print('Remote fixture file unchanged; runtime assets local; JS errors []: PASS')
        finally:browser.close()
finally:Fixture.tearDownClass()
