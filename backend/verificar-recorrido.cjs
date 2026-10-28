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
 assert.equal(objetosVideo.length,informe.videos);
 const porNombre=new Map(objetos.data.map(o=>[o.name,o]));
 for(const v of videos){const o=porNombre.get(v.id+'.mp4');assert.ok(o,'Falta objeto privado');assert.equal(Number(o.metadata.size),v.contenido.bytes);}
 const bytes=objetosVideo.reduce((n,o)=>n+Number(o.metadata.size),0);
 assert.equal(bytes,Math.round(informe.video_mib*1048576));
 videos.sort((a,b)=>a.contenido.metadata.inicio_ns-b.contenido.metadata.inicio_ns);
 for(const v of [videos[0],videos.at(-1)]){
   const enlace=await api('/dashcam/videos/'+v.id);
   assert.equal(new URL(enlace.url).origin,new URL(process.env.SUPABASE_URL).origin);
   const r=await fetch(enlace.url,{headers:{Range:'bytes=0-4095'},signal:AbortSignal.timeout(120000)});
   assert.ok([200,206].includes(r.status));
   const inicio=Buffer.from(await r.arrayBuffer());assert.equal(inicio.toString('ascii',4,8),'ftyp');
 }
 console.log(JSON.stringify({verificado:true,recorrido_id:id,registros:registros.length,muestras:muestras.length,
   videos:videos.length,bytes,frames:informe.frames_catalogados,objetos_sin_duplicados:true,
   primer_y_ultimo_mp4_accesibles:true,coincide_con_informe_local:true},null,2));
})().catch(e=>{console.error('FALLO:',e.message);process.exitCode=1;});
