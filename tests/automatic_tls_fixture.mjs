// TEST ONLY: supported Burrow context with a local CA-signed HTTPS route, not public DNS.
// Start the separate Python service using DATA/config.json first.
// Usage: NODE_EXTRA_CA_CERTS=... node tests/automatic_tls_fixture.mjs DATA CERT KEY
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { createServer } from 'node:https';
import { request } from 'node:http';
import * as extension from '../burrow/extension.mjs';
const [dataDir, cert, key]=process.argv.slice(2);
let targetPort;
const tls=createServer({cert:readFileSync(cert),key:readFileSync(key)},(req,res)=>{
 if(!targetPort){res.writeHead(503);res.end();return;}
 const r=request({host:'127.0.0.1',port:targetPort,path:req.url,method:req.method,headers:req.headers},up=>{res.writeHead(up.statusCode,up.headers);up.pipe(res);});
 r.on('error',()=>{res.writeHead(502);res.end();});req.pipe(r);
});
await new Promise(resolve=>tls.listen(9443,'127.0.0.1',resolve));
const tunnels=[];
const ctx={dataDir,domain:()=>null,dns:async()=>[],log:console.log,tunnels:{list:()=>tunnels,
 create:async spec=>{targetPort=spec.targetPort;const t={...spec,app:'robo-storage-aegis',url:'https://localhost:9443',enabled:true};tunnels.push(t);return t;},
 update:async(port,patch)=>{targetPort=patch.targetPort;return Object.assign(tunnels.find(t=>t.port===port),patch);},
 remove:async port=>{tunnels.splice(tunnels.findIndex(t=>t.port===port),1);}}};
await extension.start(ctx);
const result=await extension.handle({method:'POST',path:'/enrollment'});
if(result.json.state!=='ready')throw Error(JSON.stringify(result));
console.log('TEST ONLY: local CA-trusted HTTPS identity + nonce verified; automatic route ready. No manual URL setting.');
console.log('Descriptor:',join(dataDir,'agent-enrollment.json'));
async function stop(){await extension.stop();tls.close(()=>process.exit(0));}
process.on('SIGTERM',stop);process.on('SIGINT',stop);
