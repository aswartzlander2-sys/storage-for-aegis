"""Regression: management is original Aegis, not Robo glass or an explorer shell."""
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
with sync_playwright() as p:
 b=p.chromium.launch();page=b.new_page(viewport={'width':1440,'height':950},color_scheme='light');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://127.0.0.1:8080/');expect(page.locator('.group-card').first).to_be_visible()
 assert page.locator('#cloud-browser,.robo-admin,.robo-theme-button,link[href="assets/robo.css"],script[src="assets/robo-theme.js"]').count()==0
 assert page.locator('body').evaluate('(e)=>getComputedStyle(e).backgroundColor')=='rgb(3, 3, 4)'
 nav=page.locator('.top').evaluate('(e)=>[getComputedStyle(e).backgroundColor,getComputedStyle(e).color]')
 page.emulate_media(color_scheme='dark');assert nav==page.locator('.top').evaluate('(e)=>[getComputedStyle(e).backgroundColor,getComputedStyle(e).color]')
 page.screenshot(path=str(ROOT/'docs/aegis-original-dashboard-1.3.0.png'),full_page=True)
 page.locator('[data-act=open-group]').first.click();page.locator('[data-act=server-settings]').nth(1).click();page.locator('[data-tab=partitions]').click();expect(page.locator('.partition-disk')).to_be_visible()
 page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 box=page.locator('#modal .modal-foot').bounding_box();assert box and box['y']+box['height']<=844
 page.screenshot(path=str(ROOT/'docs/aegis-partition-mobile-1.3.0.png'))
 assert not errors,errors
 print('Original Aegis dashboard/root/layout, no Robo glass/theme buttons or explorer shell; unchanged Aegis navigation, professional planner with visible mobile footer/no page overflow: PASS; JS errors []')
 b.close()
