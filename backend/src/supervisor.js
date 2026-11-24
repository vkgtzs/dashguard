// Rutas de la aplicacion del supervisor (sesion de Supabase Auth).
const express = require('express');
const { UUID } = require('./validar');
const { expirarComandos, datos, BUCKET } = require('./dispositivo');

const PAGINA = 1000;      // maximo de filas por consulta en Supabase
const PAGINA_LISTAS = 50; // filas por pagina en las listas de la app
const DIAS_RECORRIDOS_NO_VALIDOS = 30; // despues se borran; sus alertas y evidencias se conservan
const VALIDOS = 'valido.is.null,valido.eq.true'; // null: en curso o anterior a la calificacion

// Borra recorridos no validos viejos y sus puntos. Antes desliga sus alertas y evidencias
// para no perderlas (la base las borraria junto con el recorrido). Corre a lo mas una vez al dia.
let ultimaLimpieza = 0;
async function limpiarRecorridosNoValidos(supabase) {
  if (Date.now() - ultimaLimpieza < 24 * 3600 * 1000) return;
  ultimaLimpieza = Date.now();
  const limite = new Date(Date.now() - DIAS_RECORRIDOS_NO_VALIDOS * 86400 * 1000).toISOString();
  try {
    const viejos = datos(await supabase.from('sesiones').select('id')
      .eq('valido', false).lt('inicio', limite).limit(500)).map(s => s.id);
    if (!viejos.length) return;
    datos(await supabase.from('alertas').update({ sesion_id: null }).in('sesion_id', viejos));
    datos(await supabase.from('evidencias').update({ sesion_id: null }).in('sesion_id', viejos));
    datos(await supabase.from('sesiones').delete().in('id', viejos));
    console.log(`Limpieza: ${viejos.length} recorridos no validos borrados`);
  } catch (error) {
    ultimaLimpieza = 0; // reintentar en la siguiente consulta
    console.error('Limpieza de recorridos:', error.message || error);
  }
}

async function todas(consulta) {
  const filas = [];
  for (let desde = 0; ; desde += PAGINA) {
    const pagina = datos(await consulta(desde, desde + PAGINA - 1));
    filas.push(...pagina);
    if (pagina.length < PAGINA) return filas;
  }
}

function rutasSupervisor(supabase) {
  const r = express.Router();

  r.use(async (req, res, next) => {
    const token = (req.headers.authorization || '').replace(/^Bearer /, '');
    if (!token) return res.status(401).json({ error: 'Inicia sesion' });
    const { data, error } = await supabase.auth.getUser(token);
    if (error || !data?.user) return res.status(401).json({ error: 'Sesion invalida o vencida' });
    req.usuario = data.user;
    req.dispositivos = datos(await supabase.from('dispositivos').select('id')
      .eq('supervisor_id', req.usuario.id)).map(d => d.id);
    next();
  });

  r.param('uuid', (req, res, next, valor) =>
    (UUID.test(valor) ? next() : res.status(400).json({ error: 'Identificador invalido' })));

  const esPropio = (req, dispositivo) => req.dispositivos.includes(dispositivo);
  const noEncontrado = res => res.status(404).json({ error: 'No encontrado' });

  // Lee ?dispositivo_id= y ?antes= de las listas paginadas. Responde el error y devuelve null si no son validos.
  function pagina(req, res) {
    const { dispositivo_id, antes } = req.query;
    if (dispositivo_id !== undefined && !esPropio(req, dispositivo_id)) {
      noEncontrado(res);
      return null;
    }
    if (antes !== undefined && (typeof antes !== 'string' || Number.isNaN(Date.parse(antes)))) {
      res.status(400).json({ error: 'antes debe ser una fecha ISO' });
      return null;
    }
    return { dispositivos: dispositivo_id ? [dispositivo_id] : req.dispositivos, antes };
  }

  // dispositivos, con ubicacion actual, estado y kilometraje
  r.get('/dispositivos', async (req, res) => {
    const dispositivos = datos(await supabase.from('dispositivos')
      .select('id,nombre,limite_velocidad_kmh,visto_en,posicion_latitud,posicion_longitud,posicion_velocidad_kmh,' +
              'posicion_fecha,bateria_porcentaje,bateria_cargando,bateria_fecha')
      .eq('supervisor_id', req.usuario.id).order('nombre'));
    const resumen = await Promise.all(dispositivos.map(async fila => {
      const { posicion_latitud, posicion_longitud, posicion_velocidad_kmh, posicion_fecha,
              bateria_porcentaje, bateria_cargando, bateria_fecha, ...d } = fila;
      const enRuta = datos(await supabase.from('puntos')
        .select('fecha,latitud,longitud,velocidad_kmh').eq('dispositivo_id', d.id)
        .order('fecha', { ascending: false }).limit(1).maybeSingle());
      const ultima = datos(await supabase.from('sesiones').select('fin').eq('dispositivo_id', d.id)
        .order('inicio', { ascending: false }).limit(1).maybeSingle());
      const sesiones = await todas((desde, hasta) => supabase.from('sesiones')
        .select('distancia_m').eq('dispositivo_id', d.id).or(VALIDOS).range(desde, hasta));
      // la posicion mas reciente: el ultimo punto de un recorrido o la reportada estacionado
      const estacionado = posicion_fecha && { fecha: posicion_fecha, latitud: posicion_latitud,
        longitud: posicion_longitud, velocidad_kmh: posicion_velocidad_kmh };
      const posicion = !enRuta ? estacionado || null : !estacionado ? enRuta
        : Date.parse(estacionado.fecha) > Date.parse(enRuta.fecha) ? estacionado : enRuta;
      return {
        ...d,
        ultima_posicion: posicion,
        bateria: bateria_porcentaje == null ? null
          : { porcentaje: bateria_porcentaje, cargando: Boolean(bateria_cargando), fecha: bateria_fecha },
        en_recorrido: Boolean(ultima && !ultima.fin),
        recorridos: sesiones.length,
        distancia_total_m: sesiones.reduce((total, s) => total + (s.distancia_m || 0), 0),
      };
    }));
    res.json({ dispositivos: resumen });
    limpiarRecorridosNoValidos(supabase);
  });

  r.patch('/dispositivos/:id', async (req, res) => {
    const limite = req.body?.limite_velocidad_kmh;
    if (!Number.isInteger(limite) || limite < 10 || limite > 200)
      return res.status(400).json({ error: 'El limite debe ser un entero entre 10 y 200 km/h' });
    if (!esPropio(req, req.params.id)) return noEncontrado(res);
    datos(await supabase.from('dispositivos').update({ limite_velocidad_kmh: limite }).eq('id', req.params.id));
    res.json({ id: req.params.id, limite_velocidad_kmh: limite });
  });

  // sesiones, por paginas del inicio mas reciente al mas antiguo
  // Solo los recorridos validos, salvo con ?incluir_no_validos=1
  r.get('/sesiones', async (req, res) => {
    const filtro = pagina(req, res);
    if (!filtro) return;
    let consulta = supabase.from('sesiones')
      .select('id,dispositivo_id,inicio,fin,verificacion,distancia_m,valido,conductores(nombre)')
      .in('dispositivo_id', filtro.dispositivos)
      .order('inicio', { ascending: false }).order('id', { ascending: false }).limit(PAGINA_LISTAS);
    if (req.query.incluir_no_validos !== '1') consulta = consulta.or(VALIDOS);
    if (filtro.antes) consulta = consulta.lt('inicio', filtro.antes);
    res.json({ sesiones: datos(await consulta), pagina: PAGINA_LISTAS });
  });

  r.get('/sesiones/:uuid', async (req, res) => {
    const sesion = datos(await supabase.from('sesiones')
      .select('id,dispositivo_id,inicio,fin,verificacion,distancia_m,valido,conductores(nombre)')
      .eq('id', req.params.uuid).in('dispositivo_id', req.dispositivos).maybeSingle());
    if (!sesion) return noEncontrado(res);
    const puntos = await todas((desde, hasta) => supabase.from('puntos')
      .select('fecha,latitud,longitud,velocidad_kmh').eq('sesion_id', sesion.id)
      .order('fecha').range(desde, hasta));
    res.json({ sesion, puntos });
  });

  // alertas, por paginas de la mas reciente a la mas antigua
  r.get('/alertas', async (req, res) => {
    const filtro = pagina(req, res);
    if (!filtro) return;
    let consulta = supabase.from('alertas')
      .select('id,dispositivo_id,sesion_id,tipo,fecha,latitud,longitud,detalle,leida')
      .in('dispositivo_id', filtro.dispositivos)
      .order('fecha', { ascending: false }).order('id', { ascending: false }).limit(PAGINA_LISTAS);
    if (filtro.antes) consulta = consulta.lt('fecha', filtro.antes);
    res.json({ alertas: datos(await consulta), pagina: PAGINA_LISTAS });
  });

  // cantidad de alertas sin leer de todos los vehiculos
  r.get('/alertas/pendientes', async (req, res) => {
    const { count, error } = await supabase.from('alertas').select('id', { count: 'exact', head: true })
      .in('dispositivo_id', req.dispositivos).eq('leida', false);
    if (error) throw error;
    res.json({ pendientes: count ?? 0 });
  });

  r.patch('/alertas/:uuid', async (req, res) => {
    if (typeof req.body?.leida !== 'boolean') return res.status(400).json({ error: 'leida debe ser true o false' });
    const filas = datos(await supabase.from('alertas').update({ leida: req.body.leida })
      .eq('id', req.params.uuid).in('dispositivo_id', req.dispositivos).select('id'));
    if (!filas.length) return noEncontrado(res);
    res.json({ id: req.params.uuid, leida: req.body.leida });
  });

  // comandos: foto, video o registro del rostro de un conductor
  r.post('/comandos', async (req, res) => {
    const { dispositivo_id, tipo, conductor_id } = req.body || {};
    if (!['foto', 'video', 'registro_rostro'].includes(tipo))
      return res.status(400).json({ error: 'tipo debe ser foto, video o registro_rostro' });
    if (!esPropio(req, dispositivo_id)) return noEncontrado(res);
    const fila = { dispositivo_id, tipo, solicitado_por: req.usuario.id };
    if (tipo === 'registro_rostro') {
      if (typeof conductor_id !== 'string' || !UUID.test(conductor_id))
        return res.status(400).json({ error: 'conductor_id requerido para registrar un rostro' });
      const conductor = datos(await supabase.from('conductores').select('id')
        .eq('id', conductor_id).eq('supervisor_id', req.usuario.id).eq('activo', true).maybeSingle());
      if (!conductor) return noEncontrado(res);
      fila.conductor_id = conductor_id;
    }
    const comando = datos(await supabase.from('comandos').insert(fila)
      .select('id,tipo,estado,conductor_id,creado_en').single());
    res.status(201).json({ comando });
  });

  r.get('/comandos/:uuid', async (req, res) => {
    await expirarComandos(supabase, req.dispositivos);
    const comando = datos(await supabase.from('comandos').select('id,tipo,estado,error,conductor_id,creado_en')
      .eq('id', req.params.uuid).in('dispositivo_id', req.dispositivos).maybeSingle());
    if (!comando) return noEncontrado(res);
    const evidencia = comando.estado !== 'completado' || comando.tipo === 'registro_rostro' ? null :
      datos(await supabase.from('evidencias').select('id,dispositivo_id,tipo,fecha,latitud,longitud,bytes')
        .eq('comando_id', comando.id).maybeSingle());
    res.json({ comando, evidencia });
  });

  // evidencias, por paginas de la mas reciente a la mas antigua
  r.get('/evidencias', async (req, res) => {
    const filtro = pagina(req, res);
    if (!filtro) return;
    let consulta = supabase.from('evidencias')
      .select('id,dispositivo_id,sesion_id,tipo,fecha,latitud,longitud,bytes')
      .in('dispositivo_id', filtro.dispositivos)
      .order('fecha', { ascending: false }).order('id', { ascending: false }).limit(PAGINA_LISTAS);
    if (filtro.antes) consulta = consulta.lt('fecha', filtro.antes);
    res.json({ evidencias: datos(await consulta), pagina: PAGINA_LISTAS });
  });

  // url firmada, vence en 5 min
  r.get('/evidencias/:uuid/url', async (req, res) => {
    const evidencia = datos(await supabase.from('evidencias').select('ruta,tipo')
      .eq('id', req.params.uuid).in('dispositivo_id', req.dispositivos).maybeSingle());
    if (!evidencia) return noEncontrado(res);
    const firmado = datos(await supabase.storage.from(BUCKET).createSignedUrl(evidencia.ruta, 300));
    res.json({ url: firmado.signedUrl, tipo: evidencia.tipo, expira_s: 300 });
  });

  // conductores (los descriptores faciales nunca se envian a la app)
  const CAMPOS_CONDUCTOR = 'id,nombre,activo,rostro_registrado,rostro_actualizado';
  const nombreValido = n => typeof n === 'string' && n.trim().length >= 1 && n.trim().length <= 80;

  r.get('/conductores', async (req, res) => {
    res.json({ conductores: datos(await supabase.from('conductores')
      .select(CAMPOS_CONDUCTOR).eq('supervisor_id', req.usuario.id).order('nombre')) });
  });

  r.post('/conductores', async (req, res) => {
    if (!nombreValido(req.body?.nombre)) return res.status(400).json({ error: 'Nombre de 1 a 80 caracteres' });
    const conductor = datos(await supabase.from('conductores')
      .insert({ supervisor_id: req.usuario.id, nombre: req.body.nombre.trim() })
      .select(CAMPOS_CONDUCTOR).single());
    res.status(201).json({ conductor });
  });

  r.patch('/conductores/:uuid', async (req, res) => {
    const cambios = {};
    if (req.body?.nombre !== undefined) {
      if (!nombreValido(req.body.nombre)) return res.status(400).json({ error: 'Nombre de 1 a 80 caracteres' });
      cambios.nombre = req.body.nombre.trim();
    }
    if (req.body?.activo !== undefined) {
      if (typeof req.body.activo !== 'boolean') return res.status(400).json({ error: 'activo debe ser true o false' });
      cambios.activo = req.body.activo;
    }
    if (req.body?.borrar_rostro === true) {
      Object.assign(cambios, { descriptores: null, rostro_registrado: false,
                               rostro_actualizado: new Date().toISOString() });
    }
    if (!Object.keys(cambios).length) return res.status(400).json({ error: 'Nada que cambiar' });
    const filas = datos(await supabase.from('conductores').update(cambios)
      .eq('id', req.params.uuid).eq('supervisor_id', req.usuario.id).select(CAMPOS_CONDUCTOR));
    if (!filas.length) return noEncontrado(res);
    res.json({ conductor: filas[0] });
  });

  r.delete('/conductores/:uuid', async (req, res) => {
    const filas = datos(await supabase.from('conductores').delete()
      .eq('id', req.params.uuid).eq('supervisor_id', req.usuario.id).select('id'));
    if (!filas.length) return noEncontrado(res);
    res.json({ eliminado: req.params.uuid });
  });

  return r;
}

module.exports = { rutasSupervisor };
