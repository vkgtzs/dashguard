'use strict';
(function(raiz){
 function preparar(muestras){
  const puntos=[],tramos=[];let tramo=[],anterior=null;
  for(const [indice,m] of muestras.entries()){
   const d=m.contenido?.datos||{},t=m.contenido?.boottime_ns;
   if(d.gps_valido!==true||!Number.isFinite(d.latitud)||!Number.isFinite(d.longitud)||Math.abs(d.latitud)>90||Math.abs(d.longitud)>180){
    if(tramo.length)tramos.push(tramo);tramo=[];anterior=null;continue;
   }
   const p={lat:d.latitud,lng:d.longitud,t,indice,velocidad:Number.isFinite(d.velocidad_kmh)?d.velocidad_kmh:null};
   if(anterior&&(!Number.isFinite(t)||!Number.isFinite(anterior.t)||t-anterior.t>10e9||t<=anterior.t||Math.abs(p.lng-anterior.lng)>180)){
    if(tramo.length)tramos.push(tramo);tramo=[];
   }
   puntos.push(p);tramo.push([p.lat,p.lng]);anterior=p;
  }
  if(tramo.length)tramos.push(tramo);
  return {puntos,tramos,omitidos:muestras.length-puntos.length};
 }
 function crear({contenedor,resumen,centrar,calles,estadoCalles}){
  let mapa=null,capas=null,fondo=null,limites=null;
  function quitarCalles(){if(fondo&&mapa)mapa.removeLayer(fondo);fondo=null;calles.textContent='Mostrar calles de OpenStreetMap';estadoCalles.textContent='Calles apagadas. Los puntos se dibujan localmente.';}
  function limpiar(){quitarCalles();if(capas)capas.clearLayers();limites=null;contenedor.hidden=true;centrar.disabled=true;calles.disabled=true;resumen.textContent='';}
  function encuadrar(){if(mapa&&limites){mapa.invalidateSize();mapa.fitBounds(limites,{padding:[25,25],maxZoom:17});}}
  centrar.onclick=encuadrar;
  calles.onclick=()=>{
   if(fondo){quitarCalles();return;}
   fondo=raiz.L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).addTo(mapa);
   fondo.on('tileerror',()=>{estadoCalles.textContent='No se pudieron cargar algunas calles. Los puntos GPS siguen disponibles.';});
   calles.textContent='Ocultar calles';estadoCalles.textContent='Calles de OpenStreetMap activadas (requieren Internet).';
  };
  function mostrar(muestras,inicio){
   limpiar();const datos=preparar(muestras),{puntos,tramos,omitidos}=datos;
   resumen.textContent=`${puntos.length} puntos GPS válidos de ${muestras.length} muestras; ${omitidos} sin posición utilizable. Cada punto corresponde a una muestra, aunque repita la última posición GPS. Azul: puntos y trazado; verde: inicio GPS; naranja: fin GPS. Las interrupciones de GPS no se unen.`;
   if(!puntos.length){resumen.textContent+=' Este recorrido todavía no tiene posiciones válidas.';return datos;}
   if(!raiz.L){resumen.textContent+=' No se pudo cargar la biblioteca local del mapa.';return datos;}
   contenedor.hidden=false;centrar.disabled=false;calles.disabled=false;
   if(!mapa){mapa=raiz.L.map(contenedor,{preferCanvas:true,scrollWheelZoom:false});mapa.setView([puntos[0].lat,puntos[0].lng],17);capas=raiz.L.layerGroup().addTo(mapa);raiz.L.control.scale({imperial:false}).addTo(mapa);}
   for(const tramo of tramos)if(tramo.length>1)raiz.L.polyline(tramo,{color:'#175fa6',weight:3,opacity:.65,smoothFactor:0}).addTo(capas);
   function informacion(p,etiqueta='Punto GPS'){
    const texto=document.createElement('p'),desde=Number.isFinite(inicio)&&Number.isFinite(p.t)?((p.t-inicio)/1e9).toFixed(1)+' s desde inicio':'tiempo no disponible';
    texto.textContent=`${etiqueta} · muestra ${p.indice+1} · ${desde} · ${p.lat.toFixed(6)}, ${p.lng.toFixed(6)} · ${p.velocidad===null?'velocidad no disponible':p.velocidad.toFixed(1)+' km/h'}`;return texto;
   }
   for(const p of puntos)raiz.L.circleMarker([p.lat,p.lng],{radius:4,color:'#124f8d',weight:1,fillColor:'#2995ed',fillOpacity:.8}).bindPopup(()=>informacion(p)).addTo(capas);
   for(const [p,color,texto] of [[puntos[0],'#16834a','Inicio GPS'],[puntos.at(-1),'#c96816','Fin GPS']])raiz.L.circleMarker([p.lat,p.lng],{radius:8,color,weight:3,fillOpacity:.15}).bindPopup(()=>informacion(p,texto)).addTo(capas);
   limites=raiz.L.latLngBounds(puntos.map(p=>[p.lat,p.lng]));encuadrar();return datos;
  }
  return {mostrar,limpiar};
 }
 const api={preparar,crear};if(typeof module!=='undefined'&&module.exports)module.exports=api;else raiz.DashcamMapa=api;
})(globalThis);
