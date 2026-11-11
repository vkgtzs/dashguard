// Rutas de la aplicacion web (sesion de Supabase Auth).
const express = require('express');
const { UUID } = require('./validar');
const { expirarComandos, datos, BUCKET } = require('./dispositivo');

const PAGINA = 1000; // maximo de filas por consulta en Supabase

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

  // dispositivos
  r.get('/dispositivos', async (req, res) => {
    res.json({ dispositivos: datos(await supabase.from('dispositivos')
      .select('id,nombre,limite_velocidad_kmh,visto_en').eq('supervisor_id', req.usuario.id).order('nombre')) });
  });

  r.patch('/dispositivos/:id', async (req, res) => {
    const limite = req.body?.limite_velocidad_kmh;
    if (!Number.isInteger(limite) || limite < 10 || limite > 200)
      return res.status(400).json({ error: 'El limite debe ser un entero entre 10 y 200 km/h' });
    if (!esPropio(req, req.params.id)) return noEncontrado(res);
    datos(await supabase.from('dispositivos').update({ limite_velocidad_kmh: limite }).eq('id', req.params.id));
    res.json({ id: req.params.id, limite_velocidad_kmh: limite });
  });

  // sesiones
  r.get('/sesiones', async (req, res) => {
    res.json({ sesiones: datos(await supabase.from('sesiones')
      .select('id,dispositivo_id,inicio,fin,verificacion,distancia_m,conductores(nombre)')
      .in('dispositivo_id', req.dispositivos).order('inicio', { ascending: false }).limit(100)) });
  });

  r.get('/sesiones/:uuid', async (req, res) => {
    const sesion = datos(await supabase.from('sesiones')
      .select('id,dispositivo_id,inicio,fin,verificacion,distancia_m,conductores(nombre)')
      .eq('id', req.params.uuid).in('dispositivo_id', req.dispositivos).maybeSingle());
    if (!sesion) return noEncontrado(res);
    const puntos = await todas((desde, hasta) => supabase.from('puntos')
      .select('fecha,latitud,longitud,velocidad_kmh').eq('sesion_id', sesion.id)
      .order('fecha').range(desde, hasta));
    res.json({ sesion, puntos });
  });

  // alertas
  r.get('/alertas', async (req, res) => {
    res.json({ alertas: datos(await supabase.from('alertas')
      .select('id,dispositivo_id,sesion_id,tipo,fecha,latitud,longitud,detalle,leida')
      .in('dispositivo_id', req.dispositivos).order('fecha', { ascending: false }).limit(100)) });
  });

  r.patch('/alertas/:uuid', async (req, res) => {
    if (typeof req.body?.leida !== 'boolean') return res.status(400).json({ error: 'leida debe ser true o false' });
    const filas = datos(await supabase.from('alertas').update({ leida: req.body.leida })
      .eq('id', req.params.uuid).in('dispositivo_id', req.dispositivos).select('id'));
    if (!filas.length) return noEncontrado(res);
    res.json({ id: req.params.uuid, leida: req.body.leida });
  });

  // comandos de captura
  r.post('/comandos', async (req, res) => {
    const { dispositivo_id, tipo } = req.body || {};
    if (!['foto', 'video'].includes(tipo)) return res.status(400).json({ error: 'tipo debe ser foto o video' });
    if (!esPropio(req, dispositivo_id)) return noEncontrado(res);
    const comando = datos(await supabase.from('comandos')
      .insert({ dispositivo_id, tipo, solicitado_por: req.usuario.id })
      .select('id,tipo,estado,creado_en').single());
    res.status(201).json({ comando });
  });

  r.get('/comandos/:uuid', async (req, res) => {
    await expirarComandos(supabase, req.dispositivos);
    const comando = datos(await supabase.from('comandos').select('id,tipo,estado,error,creado_en')
      .eq('id', req.params.uuid).in('dispositivo_id', req.dispositivos).maybeSingle());
    if (!comando) return noEncontrado(res);
    const evidencia = comando.estado !== 'completado' ? null :
      datos(await supabase.from('evidencias').select('id,tipo,fecha,latitud,longitud')
        .eq('comando_id', comando.id).maybeSingle());
    res.json({ comando, evidencia });
  });

  // evidencias
  r.get('/evidencias', async (req, res) => {
    res.json({ evidencias: datos(await supabase.from('evidencias')
      .select('id,dispositivo_id,sesion_id,tipo,fecha,latitud,longitud,bytes')
      .in('dispositivo_id', req.dispositivos).order('fecha', { ascending: false }).limit(100)) });
  });

  // url firmada, vence en 5 min
  r.get('/evidencias/:uuid/url', async (req, res) => {
    const evidencia = datos(await supabase.from('evidencias').select('ruta,tipo')
      .eq('id', req.params.uuid).in('dispositivo_id', req.dispositivos).maybeSingle());
    if (!evidencia) return noEncontrado(res);
    const firmado = datos(await supabase.storage.from(BUCKET).createSignedUrl(evidencia.ruta, 300));
    res.json({ url: firmado.signedUrl, tipo: evidencia.tipo, expira_s: 300 });
  });

  // conductores
  const nombreValido = n => typeof n === 'string' && n.trim().length >= 1 && n.trim().length <= 80;

  r.get('/conductores', async (req, res) => {
    res.json({ conductores: datos(await supabase.from('conductores')
      .select('id,nombre,activo,rostro_registrado').eq('supervisor_id', req.usuario.id).order('nombre')) });
  });

  r.post('/conductores', async (req, res) => {
    if (!nombreValido(req.body?.nombre)) return res.status(400).json({ error: 'Nombre de 1 a 80 caracteres' });
    const conductor = datos(await supabase.from('conductores')
      .insert({ supervisor_id: req.usuario.id, nombre: req.body.nombre.trim() })
      .select('id,nombre,activo,rostro_registrado').single());
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
    if (!Object.keys(cambios).length) return res.status(400).json({ error: 'Nada que cambiar' });
    const filas = datos(await supabase.from('conductores').update(cambios)
      .eq('id', req.params.uuid).eq('supervisor_id', req.usuario.id).select('id,nombre,activo,rostro_registrado'));
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
