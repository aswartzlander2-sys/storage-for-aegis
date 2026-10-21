// Group-scoped routing through supported Burrow APIs. Never changes global naming.
import { writeFileSync, renameSync } from 'node:fs';
import { join } from 'node:path';
import { randomBytes } from 'node:crypto';
const ID='robo-storage-aegis';
const identity=/^[a-f0-9]{16}$/;
export function primaryBase(n,d) { return d ? ((n?.active && n.prefix) ? n.prefix+'.'+d.zone : d.zone) : ''; }
export class GroupRoutes {
  constructor(ctx, helpers) { Object.assign(this,helpers); this.ctx=ctx;this.closed=false;this.states=new Map();this.probes=new Map();this.queues=new Map();this.dnsRetry=new Map();this.task=null; }
  own(port) { return this.ctx.tunnels.list().find(t=>t.port===port && t.app===ID); }
  async environment() {
    const d=this.ctx.domain(),n=d?await this.naming():null,base=primaryBase(n,d);
    const all=this.ctx.tunnels.list(), choices=new Map();
    if(base) choices.set(base,{base,zone:d.zone,kind:'primary'});
    // Only actual aliases offered by Burrow, not arbitrary DNS records or guessed labels.
    for(const t of all) {
      for(const a of t.also||[]) if(!a.hidden && !a.sub && (a.wild||a.zone)) {
        const b=a.wild||a.zone;choices.set(b,{base:b,zone:a.zone,kind:b===base?'primary':'extra'});
      }
      for(const zone of t.pickable||[]) if(!choices.has(zone)) choices.set(zone,{base:zone,zone,kind:'extra'});
    }
    return {connected:true,domain:d,domains:d?[d.zone]:[],base,naming:n,mode:d?'domain':'quick',routingBases:[...choices.values()],tunnels:all.filter(t=>t.app===ID).map(({port,url,sub,dns,quick})=>({port,url,sub,dns,quick})),note:d?'Uses Burrow’s existing domain and naming settings automatically.':'Uses Burrow’s default automatic HTTPS tunnel. No custom domain is required; its temporary address may change.'};
  }
  serialize(key, action) {
    const task=(this.queues.get(key)||Promise.resolve()).catch(()=>{}).then(action);
    this.queues.set(key,task);task.finally(()=>{if(this.queues.get(key)===task)this.queues.delete(key);}).catch(()=>{});
    return task;
  }
  publish(b) { return this.serialize(b.key,()=>this.publishOne(b)); }
  async publishOne(b) {
    if(this.closed)throw Error('Storage routing is stopping. Try again after the addon restarts.');
    if(!identity.test(b.key)||b.key!==b.group||b.server)throw Error('Publish a group; its servers inherit that group’s address.');
    if(!/^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$/.test(b.sub))throw Error('Choose a group subdomain with 1–40 letters, digits or dashes.');
    if(b.useDefaultTunnel!==undefined && typeof b.useDefaultTunnel!=='boolean')throw Error('Invalid default-tunnel option.');
    const useDefaultTunnel=b.useDefaultTunnel!==false, env=await this.environment();
    const choice=useDefaultTunnel?null:env.routingBases.find(x=>x.base===b.base);
    if(!useDefaultTunnel&&!choice)throw Error('Select a configured tunnel domain from the list, or check Use default Burrow tunnel.');
    const previous=this.load()[b.key],spec={group:b.group,server:'',sub:b.sub,useDefaultTunnel,base:choice?.base||'',zone:choice?.zone||''};
    const targetPort=await this.proxy(b.key,spec);
    if(this.closed)throw Error('Storage routing is stopping.');
    let t=previous&&this.own(previous.port);
    if(t)t=await this.ctx.tunnels.update(t.port,{sub:b.sub,targetPort,targetHost:'127.0.0.1'});
    else t=await this.ctx.tunnels.create({port:targetPort,targetPort,targetHost:'127.0.0.1',scheme:'http',name:b.name||'Robo Storage group',sub:b.sub,access:'public'});
    // Persist ownership before any further network work, including custom alias setup.
    let latest=this.load();latest[b.key]={...spec,port:t.port};this.save(latest);
    if(choice?.kind==='extra') t=await this.ctx.tunnels.update(t.port,{domains:[...new Set([...(t.domains||[]),choice.zone])]});
    this.probes.delete(b.key);this.dnsRetry.set(b.key,Date.now());
    this.states.set(b.key,await this.inspect(b.key,{...spec,port:t.port}));
    this.write();return this.states.get(b.key);
  }
  async check(url,key,t) {
    const cache=this.probes.get(key);
    if(cache?.url===url&&cache.targetPort===t.targetPort&&Date.now()-cache.at<20000)return cache;
    const nonce=randomBytes(16).toString('hex');
    const r=await fetch(url+'/route-health?probe='+nonce,{redirect:'error',signal:AbortSignal.timeout(6500)});
    if(!r.ok)return null;
    const reader=r.body.getReader(),chunks=[];let size=0;
    for(;;){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>2048){await reader.cancel();return null;}chunks.push(Buffer.from(value));}
    const h=JSON.parse(Buffer.concat(chunks).toString('utf8'));
    if(h.app!==ID||h.group!==key||h.probe!==nonce||h.ok!==true)return null;
    const result={url,targetPort:t.targetPort,at:Date.now()};this.probes.set(key,result);return result;
  }
  async inspect(key,spec) {
    let t=this.own(spec.port);
    const pending={port:spec.port,url:'',proposedUrl:'',base:spec.base||'',useDefaultTunnel:spec.useDefaultTunnel!==false,state:'pending',detail:'Burrow is preparing the group’s HTTPS address.'};
    if(!t)return {...pending,state:'missing',detail:'This group’s tunnel was removed. Launch the group to recreate it.'};
    if(t.enabled===false){this.probes.delete(key);return {...pending,detail:'The group tunnel is disabled in Burrow.'};}
    try {
      if(!this.closed&&t.dns?.error&&Date.now()-(this.dnsRetry.get(key)||0)>=60000){this.dnsRetry.set(key,Date.now());t=await this.ctx.tunnels.update(t.port,{});}
      const alias=spec.useDefaultTunnel===false?(t.also||[]).find(a=>!a.hidden&&a.url===`https://${spec.sub}.${spec.base}`):null;
      const url=spec.useDefaultTunnel===false?(alias?.url||(spec.base===this.baseFromTunnel(t)?t.url:'')):t.url;
      if(!url){this.probes.delete(key);return {...pending,detail:t.quick?.error?'Burrow tunnel: '+t.quick.error:pending.detail};}
      const parsed=new URL(url);
      if(parsed.protocol!=='https:'||parsed.username||parsed.password||parsed.search||parsed.hash||parsed.pathname!=='/')throw Error('Burrow has not supplied a valid HTTPS address.');
      pending.proposedUrl=url.replace(/\/+$/,'');
      if(spec.useDefaultTunnel!==false)pending.base=t.mode==='quick'?'':this.baseFromTunnel(t);
      if(t.dns?.ready===false){this.probes.delete(key);return {...pending,detail:'Burrow is waiting for DNS/certificate readiness.'};}
      const check=await this.check(pending.proposedUrl,key,t);
      if(!check){this.probes.delete(key);return {...pending,detail:'The address exists; waiting for an HTTPS identity check to reach this group.'};}
      return {...pending,url:pending.proposedUrl,state:'ready',checkedAt:check.at/1000,detail:'Group HTTPS route verified. All servers share this address.'};
    } catch(e){this.probes.delete(key);return {...pending,state:'pending',detail:'Waiting for Burrow HTTPS connectivity: '+String(e.cause?.code||e.message).slice(0,140)};}
  }
  baseFromTunnel(t) { try { const host=new URL(t.url).hostname;return t.sub&&host.startsWith(t.sub+'.')?host.slice(t.sub.length+1):''; } catch {return '';} }
  write() {
    if(this.closed)return;
    const groups={};
    for(const [key,spec] of Object.entries(this.load())) if(identity.test(key)&&!spec.server&&!spec.agent) {
      const value=this.states.get(key);groups[key]=value?.port===spec.port?value:{port:spec.port,state:'pending',url:'',detail:'Burrow is checking the group route.'};
    }
    const path=join(this.ctx.dataDir,'published-routes.json');writeFileSync(path+'.tmp',JSON.stringify({updated:Date.now()/1000,groups},null,2),{mode:0o600});renameSync(path+'.tmp',path);
  }
  refresh() {
    if(this.closed)return Promise.resolve();
    if(this.task)return this.task;
    this.task=(async()=>{
      const entries=Object.entries(this.load()).filter(([key,s])=>identity.test(key)&&!s.agent&&!s.server);
      for(let i=0;i<entries.length;i+=4)await Promise.all(entries.slice(i,i+4).map(async([key,spec])=>this.states.set(key,await this.inspect(key,spec))));
      this.write();
    })().finally(()=>{this.task=null;});return this.task;
  }
  async remove(key,action){return this.serialize(key,async()=>{await action();this.states.delete(key);this.probes.delete(key);this.write();});}
  async stop(){this.closed=true;await Promise.allSettled([...this.queues.values(),...(this.task?[this.task]:[])]);}
}
