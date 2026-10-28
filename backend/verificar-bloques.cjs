// Verificacion privada por streaming: nunca imprime URL, contenido o coordenadas.
require('dotenv').config({path:require('node:path').join(__dirname,'.env'),quiet:true});
const {createClient}=require('@supabase/supabase-js'),crypto=require('node:crypto');
const s=createClient(process.env.SUPABASE_URL,process.env.SUPABASE_KEY),trip='cf5d3291-7105-45cd-9fbe-323e8c945830';
(async()=>{
 const r=await s.from('dashcam_registros').select('id,contenido').eq('recorrido_id',trip).eq('device_id',process.env.DASHCAM_DEVICE_ID).eq('tipo','video');if(r.error)throw Error('Consulta no disponible');
 const c=r.data.find(v=>v.contenido.clase==='coleccion');if(!c||c.contenido.bloques.length!==6)throw Error('Falta coleccion completa');
 let total=0;
 for(const id of c.contenido.bloques){const v=r.data.find(v=>v.id===id);if(!v)throw Error('Falta bloque');const hash=crypto.createHash('sha256');let bytes=0;
 for(const p of v.contenido.partes){const u=await s.storage.from('dashguard-videos').createSignedUrl(p.ruta,300);if(u.error)throw Error('No se pudo autorizar parte');const resp=await fetch(u.data.signedUrl,{signal:AbortSignal.timeout(120000)});if(!resp.ok)throw Error('Parte inaccesible');const h=crypto.createHash('sha256');let n=0;for await(const chunk of resp.body){h.update(chunk);hash.update(chunk);n+=chunk.length;}if(n!==p.bytes||h.digest('hex')!==p.sha256)throw Error('Parte alterada');bytes+=n;}
 if(bytes!==v.contenido.bytes||hash.digest('hex')!==v.contenido.sha256)throw Error('Bloque alterado');total+=v.contenido.frames;console.log('Bloque verificado:',v.contenido.numero);}
 if(total!==26996)throw Error('Fotogramas incompletos');console.log(JSON.stringify({verificado:true,bloques:6,frames:total}));
})().catch(()=>{console.log('Verificacion incompleta; conservar todos los originales');process.exitCode=1;});

