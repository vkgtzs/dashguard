// Prueba persistente marcada como sintetica. Nunca elimina registros.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {randomUUID}=require('node:crypto');
require('dotenv').config({path:path.join(__dirname,'.env'),quiet:true});
const {digest}=require('./dashcam');
const local=process.argv[2]==='--local';
let base=local?'http://127.0.0.1':process.argv[2]||'https://dashguard-backend.onrender.com';
let servidor;
const url=new URL(base);
if(url.protocol!=='https:' && !['localhost','127.0.0.1'].includes(url.hostname))throw Error('Backend remoto requiere HTTPS');
const archivo=path.resolve(__dirname,'../../.dashcam-prueba-api-20261028.json');
let prueba;
if(fs.existsSync(archivo))prueba=JSON.parse(fs.readFileSync(archivo,'utf8'));
else {
 const id=randomUUID(),contenido_json=JSON.stringify({prueba_sintetica:true,inicio_boottime_ns:0,
  reloj:{fecha_host_utc:new Date().toISOString(),ntp_sincronizado:false},nota:'Prueba API; no es recorrido en hardware'});
 prueba={id,recorrido_id:id,tipo:'inicio',contenido_json,sha256:digest(contenido_json)};
 fs.writeFileSync(archivo,JSON.stringify(prueba),{flag:'wx'});
}
async function post(r){return fetch(base+'/dashcam/registros',{method:'POST',headers:{Authorization:'Bearer '+process.env.DASHCAM_DEVICE_TOKEN,'Content-Type':'application/json'},body:JSON.stringify({registros:[r]})});}
(async()=>{
 if(local){servidor=require('./server').listen(0,'127.0.0.1');await new Promise(r=>servidor.once('listening',r));base='http://127.0.0.1:'+servidor.address().port;}
 const health=await (await fetch(base)).json();assert.equal(health.version,'dashcam-offline-v1');
 assert.equal((await fetch(base+'/dashcam/recorridos')).status,401);
 for(let i=0;i<2;i++){const r=await post(prueba);assert.equal(r.status,200,await r.clone().text());const j=await r.json();assert.equal(j.confirmados[0].sha256,prueba.sha256);}
 const distinto=JSON.stringify({prueba_sintetica:true,distinto:true});
 assert.equal((await post({...prueba,contenido_json:distinto,sha256:digest(distinto)})).status,409);
 const r=await fetch(base+'/dashcam/recorridos/'+prueba.id,{headers:{Authorization:'Bearer '+process.env.DASHCAM_OWNER_TOKEN}});
 assert.equal(r.status,200);assert.equal((await r.json()).registros.length,1);
 console.log('OK: version, acceso anonimo denegado, persistencia, reintento unico, conflicto sin sobrescribir y consulta autenticada. Registro sintetico conservado:',prueba.id);
})().catch(e=>{console.error('FALLO:',e.message);process.exitCode=1;}).finally(()=>servidor?.close());
