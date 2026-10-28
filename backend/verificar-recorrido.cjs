// Compara la consulta real de Render y los objetos privados con el informe local.
// No imprime coordenadas, URLs firmadas ni credenciales.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
require('dotenv').config({path:path.join(__dirname,'.env'),quiet:true});
const {createClient}=require('@supabase/supabase-js');
const s=createClient(process.env.SUPABASE_URL,process.env.SUPABASE_KEY);
const informe=JSON.parse(fs.readFileSync(path.join(__dirname,'../ensayos-dashcam/reporte-inicial.json'),'utf8'));
const id=informe.recorrido_id,base='https://dashguard-backend.onrender.com';
async function api(ruta){
 const r=await fetch(base+ruta,{headers:{Authorization:'Bearer '+process.env.DASHCAM_OWNER_TOKEN},signal:AbortSignal.timeout(120000)});
 assert.equal(r.status,200);return r.json();
}
(async()=>{
 let registros=[],offset=0;
 do{const r=await api(`/dashcam/recorridos/${id}?offset=${offset}`);registros.push(...r.registros);offset=r.siguiente;}while(offset!==null);
 assert.equal(new Set(registros.map(r=>r.id)).size,registros.length,'IDs repetidos en consulta');
 const fuente=registros.filter(r=>!r.contenido.presentacion);
 const muestras=fuente.filter(r=>r.tipo==='muestra'),videos=fuente.filter(r=>r.tipo==='video');
 assert.equal(fuente.length,informe.registros,'Faltan registros del recorrido');
 assert.equal(muestras.length,informe.muestras);assert.equal(videos.length,informe.videos);
 assert.equal(muestras.filter(r=>r.contenido.datos.gps_valido===true).length,informe.gps_validas);
 assert.equal(muestras.filter(r=>r.contenido.datos.imu_valida===true).length,informe.imu_validas);
 assert.equal(videos.reduce((n,r)=>n+r.contenido.metadata.sensor_timestamps_ns.length,0),informe.frames_catalogados);
 assert.equal(registros.find(r=>r.tipo==='fin').contenido.estado,'completo');
 const prefix=`${process.env.DASHCAM_DEVICE_ID}/${id}`;
 const objetos=await s.storage.from('dashguard-videos').list(prefix,{limit:1000});
 if(objetos.error)throw objetos.error;
 const objetosVideo=objetos.data.filter(o=>o.name.endsWith('.mp4'));
 const coleccion=registros.find(v=>v.contenido.clase==='coleccion');
 let bytes=0;
 if(objetosVideo.length===informe.videos){
  const porNombre=new Map(objetosVideo.map(o=>[o.name,o]));
  for(const v of videos){const o=porNombre.get(v.id+'.mp4');assert.ok(o);assert.equal(Number(o.metadata.size),v.contenido.bytes);}
  bytes=objetosVideo.reduce((n,o)=>n+Number(o.metadata.size),0);
 }else{
  assert.equal(objetosVideo.length,0,'Limpieza incompleta de fuentes');assert.ok(coleccion,'Falta coleccion final');
  const finales=coleccion.contenido.bloques.map(id=>registros.find(v=>v.id===id));assert.equal(finales.length,6);
  assert.equal(finales.reduce((n,v)=>n+v.contenido.frames,0),informe.frames_catalogados);
  for(const v of finales){const enlace=await api('/dashcam/videos/'+v.id);assert.ok(enlace.partes.length);bytes+=v.contenido.bytes;
   for(const parte of enlace.partes){const r=await fetch(parte.url,{headers:{Range:'bytes=0-31'},signal:AbortSignal.timeout(120000)});assert.ok([200,206].includes(r.status));await r.arrayBuffer();}}
 }
 console.log(JSON.stringify({verificado:true,recorrido_id:id,registros:registros.length,muestras:muestras.length,
   videos:videos.length,bytes,frames:informe.frames_catalogados,objetos_sin_duplicados:true,
   bloques_privados_accesibles:true,coincide_con_informe_local:true},null,2));
})().catch(e=>{console.error('FALLO:',e.message);process.exitCode=1;});
