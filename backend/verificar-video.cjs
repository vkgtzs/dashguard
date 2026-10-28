// Reintento real de un segmento ya confirmado. No borra ni cambia sus bytes.
const assert=require('node:assert/strict');
require('dotenv').config({path:require('node:path').join(__dirname,'.env'),quiet:true});
const {createClient}=require('@supabase/supabase-js');
const {digest}=require('./dashcam');
const s=createClient(process.env.SUPABASE_URL,process.env.SUPABASE_KEY);
(async()=>{
 const {data,error}=await s.from('dashcam_registros').select('id,device_id,recorrido_id')
  .eq('device_id',process.env.DASHCAM_DEVICE_ID).eq('tipo','video').limit(1);
 if(error)throw error;if(!data.length)throw Error('No hay video confirmado para comprobar');
 const v=data[0],prefix=`${v.device_id}/${v.recorrido_id}`,bucket=s.storage.from('dashguard-videos');
 const antes=await bucket.list(prefix,{limit:1000});if(antes.error)throw antes.error;
 const archivo=await bucket.download(`${prefix}/${v.id}.mp4`);if(archivo.error)throw archivo.error;
 const bytes=Buffer.from(await archivo.data.arrayBuffer()),sha=digest(bytes);
 const r=await fetch(`https://dashguard-backend.onrender.com/dashcam/videos/${v.recorrido_id}/${v.id}`,{
  method:'PUT',headers:{Authorization:'Bearer '+process.env.DASHCAM_DEVICE_TOKEN,'Content-Type':'video/mp4','X-Content-Sha256':sha},body:bytes});
 assert.equal(r.status,200,await r.clone().text());assert.equal((await r.json()).sha256,sha);
 const despues=await bucket.list(prefix,{limit:1000});if(despues.error)throw despues.error;
 assert.equal(antes.data.length,despues.data.length);
 assert.deepEqual(antes.data.map(f=>f.name).sort(),despues.data.map(f=>f.name).sort());
 console.log('OK: reintento real de video conserva checksum y numero de objetos. Objetos del recorrido:',despues.data.length);
})().catch(e=>{console.error('FALLO:',e.message);process.exitCode=1;});
