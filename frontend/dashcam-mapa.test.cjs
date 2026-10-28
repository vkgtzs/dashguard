const {test}=require('node:test'),assert=require('node:assert/strict');
const {preparar}=require('./dashcam-mapa');
const muestra=(t,latitud=10,longitud=20,gps_valido=true)=>({contenido:{boottime_ns:t*1e9,datos:{latitud,longitud,gps_valido,velocidad_kmh:0}}});
test('descarta posiciones invalidas sin convertir null en cero; acepta coordenadas cero reales',()=>{
 const r=preparar([muestra(0,0,0),muestra(1,null,20),muestra(2,10,Infinity),muestra(3,91,20),muestra(4,10,-181),muestra(5,10,20,false),muestra(6,'10',20)]);
 assert.equal(r.puntos.length,1);assert.equal(r.omitidos,6);assert.equal(r.puntos[0].lat,0);
});
test('no une interrupciones de GPS ni saltos temporales superiores a diez segundos',()=>{
 const r=preparar([muestra(0),muestra(1),muestra(2,10,20,false),muestra(3),muestra(4),muestra(20),muestra(21)]);
 assert.deepEqual(r.tramos.map(t=>t.length),[2,2,2]);assert.equal(r.puntos.length,6);
});
test('conserva todos los puntos repetidos y maneja recorridos sin GPS',()=>{
 const r=preparar(Array.from({length:2000},(_,i)=>muestra(i)));
 assert.equal(r.puntos.length,2000);assert.equal(r.tramos[0].length,2000);
 assert.deepEqual(preparar([]),{puntos:[],tramos:[],omitidos:0});
 assert.equal(preparar([muestra(0,null,null,false)]).puntos.length,0);
});
