// Supported Burrow context + real local HTTP/Unix proxies; external HTTPS is mocked here.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, readFileSync, statSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createServer, request } from 'node:http';
import * as extension from '../burrow/extension.mjs';
const ID='robo-storage-aegis';
const realFetch=globalThis.fetch;
const listen=(s,...a)=>new Promise((resolve,reject)=>{s.once('error',reject);s.listen(...a,()=>resolve(s.address()));});
const close=s=>new Promise(resolve=>s.close(resolve));
async function fixture(run) {
 const data=mkdtempSync(join(tmpdir(),'robo-extension-test-')), sock=join(data,'control.sock');
 const control=createServer((req,res)=>{assert.equal(req.url,'/tunnels/naming');assert.match(req.headers['x-burrow-client'],/^robo-storage-aegis\//);res.setHeader('Content-Type','application/json');res.end(JSON.stringify({active:true,prefix:'apps'}));});
 const upstream=createServer((req,res)=>{res.setHeader('Content-Type','application/json');res.end(JSON.stringify({path:req.url,admin:req.headers['x-robo-admin']||null,authorization:req.headers.authorization||null,cookie:req.headers.cookie||null}));});
 await listen(control,sock);const addr=await listen(upstream,0,'127.0.0.1');
 writeFileSync(join(data,'config.json'),JSON.stringify({port:addr.port,bind:'127.0.0.1',version:'1.0.0',admin_key:'UNIT-TEST-NOT-A-DEPLOYMENT-SECRET',burrow_socket:sock}));
 const tunnels=[{port:1234,app:'some-other-addon',url:'https://untouched.example.com'}],removed=[];
 const f={data,tunnels,removed,reachable:true,probes:0,createFailure:false};
 globalThis.fetch=async(url,options)=>{
  if (String(url).startsWith('https://') && (new URL(url).hostname.endsWith('.apps.example.com')||new URL(url).hostname.endsWith('.example.net'))) {
   f.probes++;assert.equal(options.redirect,'error');
   return new Response(JSON.stringify({app:f.reachable?ID:'different-service',group:f.healthGroup||'a000000000000002',ok:true,probe:new URL(url).searchParams.get('probe')}));
  }
  return realFetch(url,options);
 };
 f.ctx={dataDir:data,domain:()=>({zone:'example.com',mainHost:'aegis.example.com'}),dns:async()=>[{name:'*.apps.example.com'}],tunnels:{list:()=>tunnels,create:async spec=>{if(f.createFailure)throw Error('offline test fixture');const t={...spec,enabled:true,app:ID,url:`https://${spec.sub}.apps.example.com`};tunnels.push(t);return t},update:async(port,patch)=>Object.assign(tunnels.find(t=>t.port===port),patch),remove:async port=>{removed.push(port);tunnels.splice(tunnels.findIndex(t=>t.port===port),1)}},log:()=>{}};
 f.route=async()=> (await extension.handle({method:'POST',path:'/enrollment'})).json;
 f.read=()=>JSON.parse(readFileSync(join(data,'agent-enrollment.json'),'utf8'));
 try {await run(f);} finally {await extension.stop();globalThis.fetch=realFetch;await close(control);await close(upstream);rmSync(data,{recursive:true,force:true});}
}

test('automatic HTTPS route is ready only after identity + nonce; public proxy cannot reach administration',()=>fixture(async f=>{
 await extension.start(f.ctx);
 const result=await f.route();assert.equal(result.state,'ready');assert.match(result.url,/^https:\/\/robo-agent-/);assert.ok(f.probes>=1);
 assert.equal(statSync(join(f.data,'agent-enrollment.json')).mode & 0o777,0o600);
 const t=f.tunnels.find(t=>t.app===ID);assert.equal(t.access,'public');
 for(const path of ['/','/api/state','/assets/app.js','/__gate/robo-storage/','/g/a000000000000002/']) {
  const r=await realFetch(`http://127.0.0.1:${t.targetPort}${path}`);assert.equal(r.status,404,path);
 }
 const r=await realFetch(`http://127.0.0.1:${t.targetPort}/agent/health?probe=test`,{headers:{'x-robo-admin':'spoof','cookie':'session=secret'}});
 const body=await r.json();assert.equal(body.path,'/agent/health?probe=test');assert.equal(body.admin,null);assert.equal(body.cookie,null);
 for(const path of ['/agent/../api/state','/agent/%2e%2e/api/state','/agent/%2f../api/state','//api/state','http://example.com/agent/health','/\\example.com/agent/health']) {
  const status=await new Promise((resolve,reject)=>{request({host:'127.0.0.1',port:t.targetPort,path},r=>{r.resume();resolve(r.statusCode)}).on('error',reject).end();});assert.equal(status,400,path);
 }
 const before=f.read().checkedAt;await f.route();assert.equal(f.read().checkedAt,before,'cached readiness must not renew health-check time');
 const now=Date.now;const probes=f.probes;
 try {Date.now=()=>now()+21000;f.reachable=false;assert.equal((await f.route()).state,'pending');assert.ok(f.probes>probes,'periodic checks must not use a sliding cache forever');}finally{Date.now=now;}
 assert.equal(f.read().url,'');f.reachable=true;assert.equal((await f.route()).state,'ready');
 const port=t.port,oldTarget=t.targetPort;
 await extension.stop();assert.equal(f.read().state,'pending');await extension.start(f.ctx);assert.equal((await f.route()).state,'ready');
 assert.equal(f.tunnels.filter(t=>t.app===ID).length,1);assert.equal(f.tunnels.find(t=>t.app===ID).port,port);assert.notEqual(f.tunnels.find(t=>t.app===ID).targetPort,oldTarget);
 const off=await extension.handle({method:'POST',path:'/unpublish-all'});assert.equal(off.status,200);assert.deepEqual(f.tunnels.map(t=>t.app),['some-other-addon']);
 assert.equal((await f.route()).state,'pending');assert.equal(f.tunnels.length,1,'cleanup must not recreate enrollment');
}));

test('group route remains Basic-auth preserving, group-scoped and owned; group and agent records coexist',()=>fixture(async f=>{
 await extension.start(f.ctx);await f.route();
 assert.equal(extension.mount().prefix,'/__gate/robo-storage');assert.equal(extension.mount().headers['x-robo-admin'],'UNIT-TEST-NOT-A-DEPLOYMENT-SECRET');
 const environment=await extension.handle({method:'GET',path:'/environment'});assert.equal(environment.json.base,'apps.example.com');assert.deepEqual(environment.json.domains,['example.com']);
 const publish=(base,useDefaultTunnel=false)=>extension.handle({method:'POST',path:'/publish',json:async()=>({key:'a000000000000002',group:'a000000000000002',server:'',sub:'files',base,useDefaultTunnel})});
 assert.equal((await publish('wrong.example.com')).status,400);assert.equal((await publish('apps.example.com')).status,200);
 const t=f.tunnels.find(t=>t.sub==='files');const r=await realFetch(`http://127.0.0.1:${t.targetPort}/api/files?path=folder%2Ffile.txt`,{headers:{'x-robo-admin':'spoof','authorization':'Basic TEST'}});const body=await r.json();
 assert.equal(body.path,'/g/a000000000000002/api/files?path=folder%2Ffile.txt');assert.equal(body.admin,null);assert.equal(body.authorization,'Basic TEST');
 const routes=JSON.parse(readFileSync(join(f.data,'burrow-routes.json')));assert.ok(routes._agent);assert.ok(routes.a000000000000002);
 assert.equal((await extension.handle({method:'POST',path:'/unpublish',json:async()=>({key:'_agent'})})).status,400);
 await extension.handle({method:'POST',path:'/unpublish',json:async()=>({key:'a000000000000002'})});assert.deepEqual(f.removed,[t.port]);assert.equal(f.tunnels[0].app,'some-other-addon');
}));

test('provisioning errors recover automatically, HTTP and DNS-pending routes never become ready',()=>fixture(async f=>{
 f.createFailure=true;await extension.start(f.ctx);assert.equal((await f.route()).state,'error');assert.equal(f.read().url,'');
 f.createFailure=false;assert.equal((await f.route()).state,'ready');const t=f.tunnels.find(t=>t.app===ID),url=t.url;
 t.url=url.replace('https:','http:');assert.equal((await f.route()).state,'pending');assert.equal(f.read().url,'');
 t.url=url;t.dns={ready:false};assert.equal((await f.route()).state,'pending');t.dns={ready:true};assert.equal((await f.route()).state,'ready');
 f.tunnels.splice(f.tunnels.indexOf(t),1);assert.equal((await f.route()).state,'ready');assert.equal(f.tunnels.filter(t=>t.app===ID).length,1);
}));

test('default group route ignores stale nested input and works without a linked domain',()=>fixture(async f=>{
 await extension.start(f.ctx);await f.route();
 const body={key:'a000000000000002',group:'a000000000000002',server:'',sub:'default-group',base:'wrong.nested.example.com',useDefaultTunnel:true};
 let result=await extension.handle({method:'POST',path:'/publish',json:async()=>body});assert.equal(result.status,200);assert.equal(result.json.state,'ready');assert.equal(result.json.base,'apps.example.com');
 const port=result.json.port;
 f.ctx.domain=()=>null;
 result=await extension.handle({method:'POST',path:'/publish',json:async()=>body});assert.equal(result.status,200);assert.equal(result.json.port,port);
 const env=await extension.handle({method:'GET',path:'/environment'});assert.equal(env.json.mode,'quick');assert.equal(env.json.base,'');
 // An asynchronous URL assigned after creation is picked up by the route refresher.
 const t=f.tunnels.find(t=>t.port===port);t.url='';await extension.handle({method:'POST',path:'/routes'});
 let snapshot=JSON.parse(readFileSync(join(f.data,'published-routes.json')));assert.equal(snapshot.groups[body.group].url,'');
 t.url='https://assigned-later.apps.example.com';await extension.handle({method:'POST',path:'/routes'});
 snapshot=JSON.parse(readFileSync(join(f.data,'published-routes.json')));assert.equal(snapshot.groups[body.group].state,'ready');assert.equal(snapshot.groups[body.group].url,t.url);
}));

test('group identity mismatch stays pending; concurrent launches share one tunnel',()=>fixture(async f=>{
 await extension.start(f.ctx);await f.route();
 const body={key:'a000000000000002',group:'a000000000000002',server:'',sub:'serial-group',useDefaultTunnel:true};
 const publish=()=>extension.handle({method:'POST',path:'/publish',json:async()=>body});
 f.healthGroup='a000000000000099';let result=await publish();assert.equal(result.json.state,'pending');assert.equal(result.json.url,'');
 f.healthGroup=body.group;
 const results=await Promise.all(Array.from({length:5},publish));assert.ok(results.every(r=>r.status===200&&r.json.state==='ready'));
 assert.equal(f.tunnels.filter(t=>t.sub===body.sub).length,1);
 const t=f.tunnels.find(t=>t.sub===body.sub);t.enabled=false;await extension.handle({method:'POST',path:'/routes'});
 const snapshot=JSON.parse(readFileSync(join(f.data,'published-routes.json')));assert.equal(snapshot.groups[body.group].url,'');assert.equal(snapshot.groups[body.group].state,'pending');
}));

test('server-specific routes are rejected and custom bases must be offered by Burrow',()=>fixture(async f=>{
 await extension.start(f.ctx);await f.route();
 const body={key:'a000000000000002',group:'a000000000000002',sub:'custom',useDefaultTunnel:false,base:'unconfigured.example.com'};
 const publish=b=>extension.handle({method:'POST',path:'/publish',json:async()=>b});
 assert.equal((await publish(body)).status,400);
 assert.equal((await publish({...body,server:'a000000000000003'})).status,400);
 assert.equal((await publish({...body,base:'apps.example.com'})).json.state,'ready');
}));

test('configured extra wildcard alias is selected without changing primary/global naming',()=>fixture(async f=>{
 await extension.start(f.ctx);await f.route();
 const agent=f.tunnels.find(t=>t.sub?.startsWith('robo-agent-'));
 agent.also=[{zone:'example.net',wild:'media.example.net',url:`https://${agent.sub}.media.example.net`}];
 const create=f.ctx.tunnels.create;
 f.ctx.tunnels.create=async spec=>{const t=await create(spec);t.also=[{zone:'example.net',wild:'media.example.net',url:`https://${spec.sub}.media.example.net`}];return t;};
 const b={key:'a000000000000002',group:'a000000000000002',sub:'custom',useDefaultTunnel:false,base:'media.example.net'};
 const result=await extension.handle({method:'POST',path:'/publish',json:async()=>b});assert.equal(result.status,200);assert.equal(result.json.state,'ready');assert.equal(result.json.url,'https://custom.media.example.net');
 const t=f.tunnels.find(t=>t.sub==='custom');assert.deepEqual(t.domains,['example.net']);assert.equal(t.url,'https://custom.apps.example.com');assert.equal(f.ctx.domain().zone,'example.com');
}));
