"""Synthetic 512 GB physical / 1 GB allocation browser regression. No provider or disk modification.
Usage: python tests/ui_quota_regression.py [http://127.0.0.1:8080/manage]
"""
import json
from pathlib import Path
import sys
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]
URL=sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8080/manage'
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':1100});errors=[];scenario=1
    page.on('pageerror',lambda e:errors.append(str(e)))
    def fixture(route):
        response=route.fetch();state=response.json();g=state['groups'][0]
        s=next(s for s in state['servers'] if s['group']==g['id'] and s['kind']=='linux')
        s.update(name='Synthetic quota regression disk',capacity=512_000_000_000,physicalCapacity=512_000_000_000,limit=1_000_000_000,allocationLimit=1_000_000_000,allocatedCapacity=1_000_000_000,remainingAllocation=750_000_000,used=250_000_000,inventory=[],partitions=[],types={'other':250_000_000})
        servers=[s]
        if scenario==2:
            second={**s,'id':'b0000000000000ab','name':'Three GB allocation','capacity':3_000_000_000,'physicalCapacity':3_000_000_000,'limit':3_000_000_000,'allocationLimit':3_000_000_000,'allocatedCapacity':3_000_000_000,'used':1_500_000_000,'types':{'audio':1_500_000_000}}
            unknown={**s,'id':'b0000000000000ac','name':'Unknown capacity','capacity':0,'physicalCapacity':0,'limit':0,'allocationLimit':0,'allocatedCapacity':0,'used':0,'types':{}}
            servers += [second,unknown]
        state.update(groups=[g],servers=servers);route.fulfill(response=response,body=json.dumps(state))
    page.route('**/api/state',fixture)
    page.goto(URL)
    expect(page.locator('.stat').filter(has_text='Total allocation').locator('.stat-value')).to_have_text('1.0 GB')
    expect(page.locator('.group-capacity')).to_contain_text('1.0 GB allocated')
    expect(page.locator('.server-row .capacity-label')).to_contain_text('250.0 MB of 1.0 GB')
    expect(page.locator('.server-row .capacity-label')).to_contain_text('25%')
    page.locator('[data-act=open-group]').click()
    expect(page.locator('.server-detail-head')).to_contain_text('Allocation ceiling 1.0 GB')
    expect(page.locator('.server-detail-head')).to_contain_text('Physical capacity 512.0 GB')
    expect(page.locator('.big-bar').first).to_contain_text('1.0 GB')
    ratio=page.locator('.usage-bar').evaluate('(e)=>e.querySelector(".usage-segment").getBoundingClientRect().width/e.clientWidth');assert abs(ratio-.25)<.002,ratio
    assert page.locator('.big-bar').first.evaluate('(e)=>e.getBoundingClientRect().height')==150
    assert page.locator('.usage-bar').evaluate('(e)=>e.getBoundingClientRect().height')==75
    scenario=2;page.reload();page.locator('[data-act=open-group]').click()
    ratios=page.locator('.big-bar').first.evaluate('(e)=>[...e.querySelectorAll(".bar-section")].map(s=>s.getBoundingClientRect().width/e.clientWidth)')
    assert len(ratios)==3 and abs(ratios[0]-.25)<.002 and abs(ratios[1]-.75)<.002 and ratios[2]==0,ratios
    page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    ratios=page.locator('.big-bar').first.evaluate('(e)=>[...e.querySelectorAll(".bar-section")].map(s=>s.getBoundingClientRect().width/e.clientWidth)');assert abs(ratios[0]-.25)<.01 and abs(ratios[1]-.75)<.01,ratios
    page.screenshot(path=str(ROOT/'docs/quota-regression-1.3.0.png'),full_page=True)
    assert not errors,errors
    print('SYNTHETIC 512 GB / 1 GB UI: total allocation, group contribution, server bar = 1.0 GB; 250 MB = 25%; physical 512 GB labeled separately; measured server fill 25%, 150/75px heights, group segments 25/75/0% on desktop/mobile; JavaScript errors: []')
    browser.close()
