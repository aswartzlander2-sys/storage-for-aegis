"""Synthetic 512 GB physical / 1 GB allocation browser regression. No provider or disk modification.
Usage: python tests/ui_quota_regression.py [http://127.0.0.1:8080/]
"""
import json
from pathlib import Path
import sys
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]
URL=sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8080/'
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':1100});errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    def fixture(route):
        response=route.fetch();state=response.json();g=state['groups'][0]
        s=next(s for s in state['servers'] if s['group']==g['id'] and s['kind']=='linux')
        s.update(name='Synthetic quota regression disk',capacity=512_000_000_000,physicalCapacity=512_000_000_000,limit=1_000_000_000,allocationLimit=1_000_000_000,allocatedCapacity=1_000_000_000,remainingAllocation=750_000_000,used=250_000_000,inventory=[],partitions=[],types={'other':250_000_000})
        state.update(groups=[g],servers=[s]);route.fulfill(response=response,body=json.dumps(state))
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
    page.screenshot(path=str(ROOT/'docs/quota-regression-1.1.0.png'),full_page=True)
    assert not errors,errors
    print('SYNTHETIC 512 GB / 1 GB UI: total allocation, group contribution, server bar = 1.0 GB; 250 MB = 25%; physical 512 GB labeled separately; JavaScript errors: []')
    browser.close()
