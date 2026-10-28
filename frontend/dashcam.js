'use strict';
const $=id=>document.getElementById(id);
let clave='',backend='',seleccion=null,blobURL=null,carga=null;
function liberarVideo(){carga?.abort();carga=null;if(blobURL){URL.revokeObjectURL(blobURL);blobURL=null;}$('descargar').hidden=true;$('reproductor').removeAttribute('src');$('reproductor').load();}
const sha=async b=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',b)),v=>v.toString(16).padStart(2,'0')).join('');
async function reproducir(v){
 liberarVideo();const control=new AbortController();carga=control;
 try{avisar('Preparando MP4 privado…');const r=await api('/dashcam/videos/'+v.id);if(control.signal.aborted)return;let url=r.url;
 if(r.partes){const buffers=[];for(const [i,p] of r.partes.entries()){avisar(`Descargando bloque ${v.contenido.numero}: parte ${i+1}/${r.partes.length}…`);const resp=await fetch(p.url,{signal:control.signal});if(!resp.ok)throw Error('No se pudo descargar el bloque');const b=await resp.arrayBuffer();if(b.byteLength!==p.bytes||await sha(b)!==p.sha256)throw Error('Integridad de video no verificada');buffers.push(b);}
 const blob=new Blob(buffers,{type:'video/mp4'});if(blob.size!==r.bytes||await sha(await blob.arrayBuffer())!==r.sha256)throw Error('El MP4 no coincide con el original');if(control.signal.aborted)return;blobURL=URL.createObjectURL(blob);url=blobURL;}
 $('reproductor').src=url;$('reproductor').load();$('descargar').href=url;$('descargar').download=r.archivo||'segmento.mp4';$('descargar').hidden=false;avisar('MP4 listo. Puedes reproducirlo o descargarlo.');
 }catch(e){if(e.name!=='AbortError')avisar(e.message);}
}
const avisar=t=>$('estado').textContent=t;
function boton(texto,accion,contenedor){const b=document.createElement('button');b.textContent=texto;b.onclick=accion;contenedor.append(b);return b;}
async function api(ruta){
 const r=await fetch(backend+ruta,{headers:{Authorization:'Bearer '+clave},cache:'no-store'});
 const datos=await r.json();if(!r.ok)throw Error(datos.error||`HTTP ${r.status}`);return datos;
}
$('conexion').onsubmit=async e=>{
 e.preventDefault();
 try{
  const u=new URL($('backend').value);
  if(u.protocol!=='https:' && !['localhost','127.0.0.1'].includes(u.hostname))throw Error('Backend remoto requiere HTTPS');
  if(u.username||u.password||u.search||u.hash||!['','/'].includes(u.pathname))throw Error('Indica solo el origen del backend');
  backend=u.origin;clave=$('clave').value;$('clave').value='';
  await listar();
 }catch(e){avisar(e.message);}
};
async function listar(){
 try{
  if(!clave)throw Error('Conecta primero con la clave del propietario');
  avisar('Consultando nube…');const {registros}=await api('/dashcam/recorridos');
  const grupos=new Map();for(const r of registros){const t=grupos.get(r.recorrido_id)||{};t[r.tipo]=r;grupos.set(r.recorrido_id,t);}
  $('recorridos').replaceChildren();
  for(const [id,t] of grupos){
    const fecha=t.inicio?.contenido.reloj?.fecha_host_utc||'inicio todavía pendiente';
    boton(`${t.inicio?.contenido.prueba_sintetica?'Prueba sintética · ':''}${fecha} · ${t.fin?.contenido.estado||'abierto o cierre pendiente'} · ${id.slice(0,8)}`,()=>detalle(id),$('recorridos'));
  }
  avisar(`${grupos.size} recorridos recibidos. La hora mostrada procede del reloj del equipo; consulta su estado NTP.`);
 }catch(e){avisar(e.message);}
}
$('recargar').onclick=listar;
async function detalle(id){
 try{
  seleccion=id;avisar('Descargando metadatos del recorrido…');let registros=[],offset=0;
  do{const r=await api(`/dashcam/recorridos/${id}?offset=${offset}`);registros.push(...r.registros);offset=r.siguiente;}while(offset!==null);
  registros=[...new Map(registros.map(r=>[r.id,r])).values()];
  const inicio=registros.find(r=>r.tipo==='inicio')?.contenido;
  const fin=registros.find(r=>r.tipo==='fin')?.contenido;
  const muestras=registros.filter(r=>r.tipo==='muestra').sort((a,b)=>a.contenido.boottime_ns-b.contenido.boottime_ns);
  const coleccion=registros.find(r=>r.tipo==='video'&&r.contenido.clase==='coleccion');
  const originales=registros.filter(r=>r.tipo==='video'&&!r.contenido.presentacion);
  const videos=(coleccion?coleccion.contenido.bloques.map(id=>registros.find(r=>r.id===id)).filter(Boolean):originales).sort((a,b)=>a.contenido.metadata.inicio_ns-b.contenido.metadata.inicio_ns);
  $('detalle').hidden=false;$('titulo').textContent='Recorrido '+id;
  const duracion=fin&&inicio?(fin.fin_boottime_ns-inicio.inicio_boottime_ns)/1e9:null;
  const segundosVideo=videos.reduce((total,v)=>total+v.contenido.metadata.sensor_timestamps_ns.length,0)/15;
  $('resumen').textContent=`Estado: ${fin?.estado||'abierto o cierre aún pendiente'}. Duración de la sesión: ${duracion===null?'pendiente':duracion.toFixed(1)+' s'}. Video recibido: ${segundosVideo.toFixed(1)} s nominales. ${videos.length} videos y ${muestras.length} muestras recibidas. Reloj NTP al inicio: ${inicio?.reloj?.ntp_sincronizado?'sincronizado':'no verificado'}. ${fin?.parciales?.length?'Existen segmentos parciales por recuperar.':''}`;
  $('videos').replaceChildren();
  videos.forEach((v,i)=>boton(`${coleccion||v.contenido.segundos_solicitados===300?'Bloque':'Segmento'} ${i+1} · ${(v.contenido.metadata.sensor_timestamps_ns.length/15/60).toFixed(2)} min · ${(v.contenido.bytes/1048576).toFixed(2)} MiB`,()=>reproducir(v),$('videos')));
  if(!coleccion&&fin&&segundosVideo>=300)boton('Preparar seis bloques de 5 minutos',async()=>{try{const r=await fetch(backend+`/dashcam/recorridos/${id}/exportar`,{method:'POST',headers:{Authorization:'Bearer '+clave}});if(!r.ok)throw Error('No se pudo iniciar la preparación');avisar('Preparando bloques en la nube. Actualiza el recorrido en unos minutos.');}catch(e){avisar(e.message);}},$('videos'));
  $('sensores').textContent=`GPS válido: ${muestras.filter(m=>m.contenido.datos.gps_valido).length}/${muestras.length}. IMU válida: ${muestras.filter(m=>m.contenido.datos.imu_valida===true).length}/${muestras.length}. Aceleración incluye gravedad.`;
  function pagina(indice){$('muestras').replaceChildren();$('paginas').replaceChildren();
  if(indice>0)boton('Anteriores',()=>pagina(indice-1),$('paginas'));
  const etiqueta=document.createElement('span');etiqueta.textContent=` Muestras ${indice*100+1}–${Math.min((indice+1)*100,muestras.length)} de ${muestras.length} `;$('paginas').append(etiqueta);
  if((indice+1)*100<muestras.length)boton('Siguientes',()=>pagina(indice+1),$('paginas'));
  for(const m of muestras.slice(indice*100,(indice+1)*100)){
   const d=m.contenido.datos,tr=document.createElement('tr');
   const valores=[inicio?((m.contenido.boottime_ns-inicio.inicio_boottime_ns)/1e9).toFixed(1):'—',d.gps_valido?`${d.latitud}, ${d.longitud}`:'sin posición',d.velocidad_kmh??'—',d.imu_valida?'válida':d.imu_error||'no verificada',d.magnitud_ms2??'—'];
   valores.forEach(v=>{const td=document.createElement('td');td.textContent=String(v);tr.append(td);});$('muestras').append(tr);
  }
  }pagina(0);
  avisar('Datos recibidos de la nube. Conteos parciales hasta que termine la sincronización.');
 }catch(e){avisar(e.message);}
}
$('actualizar').onclick=()=>seleccion&&detalle(seleccion);
$('desconectar').onclick=()=>{clave='';seleccion=null;liberarVideo();$('reproductor').removeAttribute('src');$('reproductor').load();$('recorridos').replaceChildren();$('muestras').replaceChildren();$('videos').replaceChildren();$('detalle').hidden=true;avisar('Consulta cerrada. Clave eliminada de la memoria de esta página.');};
