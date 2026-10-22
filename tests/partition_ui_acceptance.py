"""Planner regressions after cloud_ui_acceptance.py; disposable private runtime only."""
import json,sys
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];DATA=Path(sys.argv[1]).resolve();assert DATA.name=='cloud-test-runtime'
config=json.loads((DATA/'config.json').read_text());BASE='http://127.0.0.1:8800'
with sync_playwright() as p:
 b=p.chromium.launch();ctx=b.new_context(extra_http_headers={'X-Robo-Admin':config['admin_key'],'X-Robo-Request':'1'},viewport={'width':1440,'height':950});page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d:d.accept())
 def api(path,body=None):
  r=ctx.request.get(BASE+'/'+path) if body is None else ctx.request.post(BASE+'/'+path,data=body)
  assert r.ok,(r.status,r.text());return r.json()
 def getserver():return next(s for s in api('api/state')['servers'] if s['id']==sid)
 state=api('api/state');g=state['groups'][-1];s=next(s for s in state['servers'] if s['group']==g['id'] and s['name']=='Design test worker');sid=s['id'];original_inventory=s['inventory']
 api('api/servers/'+sid+'/partition',{'name':'Empty archive','path':'empty','limit':400000000});api('api/servers/'+sid+'/partition',{'name':'Small nested budget','path':'empty/nested','limit':8});api('api/servers/'+sid+'/partition',{'name':'Hidden partition','path':'private/empty','limit':100000000})
 page.goto(BASE+'/');expect(page.locator('.group-card').first).to_be_visible();page.evaluate('(id)=>openPartitionManager(id)',sid)
 page.locator('[data-plan=select][data-path="empty/nested"]').last.click();page.locator('#partition-unit').select_option('1');page.locator('#partition-size').fill('3');page.locator('[data-plan=queue]').click();expect(page.locator('#modal-error')).to_contain_text('below existing file usage')
 assert next(x for x in getserver()['partitions'] if x['path']=='empty/nested')['limit']==8
 page.locator('[data-plan=select][data-path=empty]').last.click();page.locator('#partition-unit').select_option('1');slider=page.locator('#partition-slider');slider.focus();slider.press('End');assert int(slider.input_value())>400000000
 page.locator('#partition-size').fill('300000000');page.locator('[data-plan=queue]').click();expect(page.locator('[data-plan=review]')).to_be_enabled()
 assert next(x for x in getserver()['partitions'] if x['path']=='empty')['limit']==400000000
 page.locator('[data-plan=undo]').click();expect(page.locator('[data-plan=review]')).to_be_disabled()
 page.locator('[data-plan=select][data-path=empty]').last.click();page.locator('#partition-size').fill('0.3');page.locator('[data-plan=queue]').click()
 page.locator('[data-plan=select][data-path="private/empty"]').last.click();page.locator('[data-plan=remove]').click();page.locator('[data-plan=review]').click();page.locator('#partition-ack').check()
 with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/partitions')) as applied:page.locator('[data-plan=apply]').click()
 assert applied.value.ok,applied.value.text();expect(page.locator('[data-plan=new]').last).to_be_enabled();updated=getserver();assert len(updated['partitions'])==2 and updated['inventory']==original_inventory
 # Concurrent edits are rejected rather than silently overwritten.
 page.locator('[data-plan=select][data-path=empty]').last.click();page.locator('#partition-size').fill('0.2');page.locator('[data-plan=queue]').click()
 api('api/servers/'+sid+'/partition',{'name':'Concurrent edit','path':'empty','limit':250000000})
 page.locator('[data-plan=review]').click();page.locator('#partition-ack').check()
 with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/partitions')) as stale:page.locator('[data-plan=apply]').click()
 assert stale.value.status==409;expect(page.locator('#modal-error')).to_contain_text('changed');assert next(x for x in getserver()['partitions'] if x['path']=='empty')['limit']==250000000
 page.locator('[data-act=close-modal]').first.click();page.evaluate('()=>refresh()');page.evaluate('(id)=>openPartitionManager(id)',sid)
 page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 foot=page.locator('[data-plan=review]').bounding_box();assert foot and foot['y']+foot['height']<=844
 page.screenshot(path=str(ROOT/'docs/partition-mobile-1.3.0.png'))
 files=b.new_context(http_credentials={'username':'design-tester','password':'DISPOSABLE-UI-test-password'},viewport={'width':1440,'height':950});explorer=files.new_page();explorer.goto(BASE+'/g/'+g['id']+'/');folder_card=explorer.locator('#fileGrid > div').filter(has=explorer.locator('h4',has_text='empty'));expect(folder_card).to_contain_text('Partition');explorer.screenshot(path=str(ROOT/'docs/partition-folders-1.3.0.png'));files.close()
 assert not errors,errors
 print('Planner: keyboard size slider, below-usage rejection, queue without mutation, undo, resize, metadata-only removal preserving files, concurrent-plan HTTP 409 and 390px visible footer/no page overflow and order-independent partition-folder labels: PASS; JS errors []')
 b.close()
