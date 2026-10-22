"""Robo management theme is scoped inside the unchanged Aegis navigation. Demo only."""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':1100},color_scheme='light');errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8080/manage')
    expect(page.locator('.group-card').first).to_be_visible()
    nav=page.locator('.top').evaluate('(e)=>[getComputedStyle(e).backgroundColor,getComputedStyle(e).color]')
    light=page.locator('.robo-admin').evaluate('(e)=>getComputedStyle(e).color')
    assert page.locator('.robo-admin .card').first.evaluate('(e)=>getComputedStyle(e).backdropFilter')!='none'
    page.screenshot(path=str(ROOT/'docs/robo-management-light-1.2.0.png'),full_page=True)
    page.get_by_label('Switch to dark theme',exact=True).click()
    expect(page.locator('html')).to_have_attribute('data-robo-theme','dark')
    assert page.locator('.robo-admin').evaluate('(e)=>getComputedStyle(e).color')!=light
    assert page.locator('.top').evaluate('(e)=>[getComputedStyle(e).backgroundColor,getComputedStyle(e).color]')==nav
    page.reload();expect(page.locator('html')).to_have_attribute('data-robo-theme','dark')
    expect(page.locator('.group-card').first).to_be_visible()
    page.screenshot(path=str(ROOT/'docs/robo-management-dark-1.2.0.png'),full_page=True)
    page.locator('[data-act=add-server]').first.click();expect(page.locator('#modal')).to_have_class('robo-admin-dialog')
    assert page.locator('#modal').evaluate('(e)=>getComputedStyle(e).color')==page.locator('.robo-admin').evaluate('(e)=>getComputedStyle(e).color')
    page.get_by_label('Close dialog',exact=True).click()
    page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(ROOT/'docs/robo-management-mobile-1.2.0.png'),full_page=True)
    assert not errors,errors
    print('Robo management glass panels, light/dark persistence, dialog theme, 390px mobile/no overflow: PASS')
    print('Aegis top navigation computed colors unchanged across Robo theme switch; JavaScript errors: []')
    browser.close()
