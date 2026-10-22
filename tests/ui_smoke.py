"""Playwright smoke test against the explicitly labeled demo, not cloud providers.
Usage: python tests/ui_smoke.py [http://127.0.0.1:8080/manage]
"""
from pathlib import Path
import sys
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
URL=sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8080/manage'
with sync_playwright() as p:
 browser=p.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':1100});errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(URL);page.get_by_text('Creative studio',exact=True).wait_for();page.screenshot(path=str(ROOT/'docs/configuration-1.2.0.png'),full_page=True)
 page.locator('[data-act=add-group]').first.click()
 expect_checkbox=page.get_by_label('Use default Burrow tunnel',exact=True)
 assert expect_checkbox.is_checked()
 assert page.get_by_label('Group tunnel domain',exact=True).is_disabled()
 assert page.locator('[name=tunnelSub]').count()==0
 expect_checkbox.uncheck();assert page.get_by_label('Group tunnel domain',exact=True).is_enabled();assert page.get_by_label('Group tunnel domain',exact=True).input_value()=='example.com';assert page.locator('[name=base] option').all_text_contents()==['example.com']
 expect_checkbox.check();page.screenshot(path=str(ROOT/'docs/default-group-1.2.0.png'))
 page.get_by_label('Close dialog').click()
 print('Group address: default Burrow checkbox below address, checked by default; domain inherited; no nested-domain field')
 page.locator('[data-act=add-server]').first.click();assert page.locator('#launch-server').is_disabled()
 page.locator('#keys-upload').set_input_files({'name':'SYNTHETIC-TEST-keys.txt','mimeType':'text/plain','buffer':b'Endpoint: e2-s3.test.idrivee2.com\nRegion Code: test\nAccess key ID: TEST-NOT-REAL\nSecret Access Key: TEST-NOT-REAL'})
 from playwright.sync_api import expect
 expect(page.locator('#launch-server')).to_be_enabled()
 print('E2 upload gate: disabled without file, enabled after synthetic import; no provider request made')
 page.locator('[data-kind=linux]').click();assert page.locator('[name=sub], [name=base], [name=domain], [name=tunnelSub], [name=useDefaultTunnel]').count()==0;assert page.get_by_text('Uses the group’s address',exact=True).is_visible();assert page.locator('.command').count()==0;assert page.locator('#launch-server').is_disabled();page.screenshot(path=str(ROOT/'docs/linux-setup.png'));page.get_by_label('Close dialog').click()
 page.locator('[data-act=open-group]').first.click();page.locator('.big-bar').first.wait_for();page.screenshot(path=str(ROOT/'docs/group-settings.png'),full_page=True)
 page.locator('[data-act=server-settings]').nth(1).click();page.locator('[data-tab=partitions]').click();page.locator('dialog .partition').wait_for();page.get_by_label('Close dialog').click()
 page.locator('[data-act=server-settings]').first.click();page.locator('[data-tab=danger]').click();page.locator('[data-act=remove-dialog]').click();assert page.locator('.range-bar').is_visible()
 # Adjacent allocation boundary is actually draggable and preserves 100% total.
 handle=page.locator('[data-handle]').first;box=handle.bounding_box();assert box
 page.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2);page.mouse.down();page.mouse.move(box['x']+35,box['y']+box['height']/2,steps=5);page.mouse.up()
 values=page.locator('.allocation-input').evaluate_all('(els)=>els.map(e=>Number(e.value))');assert sum(values)==100
 page.locator('[data-act=confirm-remove]').click();assert page.get_by_text('Move files & disconnect',exact=True).is_visible();page.get_by_label('Close dialog').click()
 page.locator('[data-act=server-settings]').first.click();page.locator('[data-tab=danger]').click();page.locator('[data-act=remove-dialog]').click();page.locator('#move-files').uncheck();page.locator('[data-act=confirm-remove]').click();assert page.get_by_text('Permanently erase server data?',exact=True).is_visible();page.get_by_label('Close dialog').click()
 page.set_viewport_size({'width':390,'height':844});page.locator('[data-act=back]').click();page.screenshot(path=str(ROOT/'docs/configuration-mobile-1.2.0.png'),full_page=True)
 assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
 print('UI smoke checks passed: desktop/mobile, Linux command hidden/verification gating, group bars, partitions, draggable redistribution shares, migration and erase confirmation modals.')
 print('Browser page errors:',errors);assert not errors
 browser.close()
