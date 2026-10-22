// Signed-in Burrow addon panel. The full dashboard is mounted by extension.mjs.
let summary=null,at=0,busy=false,error='';
export function card(ctx){
 if(!busy&&Date.now()-at>15000){busy=true;ctx.api('/summary').then(s=>{summary=s;error=''}).catch(e=>{error=e.message}).finally(()=>{busy=false;at=Date.now();ctx.render()})}
 const h=ctx.h;
 return `<section class="card lit" style="padding:20px"><div style="display:flex;align-items:center;gap:15px;flex-wrap:wrap"><img src="/__gate/api/addons/robo-storage-aegis/image" alt="" width="44" height="44" style="border-radius:12px"><div style="flex:1"><h3>Robo Cloud</h3><p class="muted small">${error?h(error):summary?`${summary.groups} groups · ${summary.servers} storage servers · ${(summary.used/1e9).toFixed(1)} GB used`:'Storage groups, quotas and directory permissions.'}</p></div><a class="btn primary" href="/__gate/robo-storage/">Open Robo Cloud ↗</a></div></section>`;
}
export function wire(){}
