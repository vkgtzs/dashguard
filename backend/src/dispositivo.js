// Rutas de la Raspberry (token de dispositivo).
const crypto = require('node:crypto');
const express = require('express');
const { validarRegistro, UUID, SHA256 } = require('./validar');

const BUCKET = 'dashguard-evidencias';
const EXTENSION = { 'image/jpeg': 'jpg', 'video/mp4': 'mp4' };
const SEGUNDOS_VIGENCIA_COMANDO = 120;

const digest = x => crypto.createHash('sha256').update(x).digest('hex');
const rutaArchivo = (dispositivo, id, tipo) => `${dispositivo}/${id}.${tipo === 'foto' ? 'jpg' : 'mp4'}`;

function datos(respuesta) {
  if (respuesta.error) throw respuesta.error;
  return respuesta.data;
}

async function expirarComandos(supabase, dispositivos) {
  if (!dispositivos.length) return;
  const limite = new Date(Date.now() - SEGUNDOS_VIGENCIA_COMANDO * 1000).toISOString();
  datos(await supabase.from('comandos')
    .update({ estado: 'expirado', actualizado_en: new Date().toISOString() })
    .in('dispositivo_id', dispositivos).eq('estado', 'pendiente').lt('creado_en', limite));
}

async function aplicar(supabase, dispositivo, { id, tipo, datos: d }) {
  const insertar = (tabla, fila) =>
    supabase.from(tabla).upsert(fila, { onConflict: 'id', ignoreDuplicates: true });

  switch (tipo) {
    case 'sesion_inicio':
      return datos(await insertar('sesiones',
        { id: d.sesion_id, dispositivo_id: dispositivo.id, inicio: d.fecha }));

    case 'verificacion': {
      let conductor = null;
      if (d.conductor_id) {
        conductor = datos(await supabase.from('conductores').select('id')
          .eq('id', d.conductor_id).eq('supervisor_id', dispositivo.supervisor_id).maybeSingle());
      }
      return datos(await supabase.from('sesiones')
        .update({ verificacion: d.resultado, conductor_id: conductor?.id ?? null })
        .eq('id', d.sesion_id).eq('dispositivo_id', dispositivo.id));
    }

    case 'sesion_fin':
      return datos(await supabase.from('sesiones')
        .update({ fin: d.fecha, distancia_m: d.distancia_m })
        .eq('id', d.sesion_id).eq('dispositivo_id', dispositivo.id));

    case 'punto':
      return datos(await insertar('puntos', { id, dispositivo_id: dispositivo.id, ...d }));

    case 'alerta':
      return datos(await insertar('alertas', { id, dispositivo_id: dispositivo.id, ...d }));

    case 'evidencia': {
      let comando = null;
      if (d.comando_id) {
        comando = datos(await supabase.from('comandos').select('id')
          .eq('id', d.comando_id).eq('dispositivo_id', dispositivo.id).maybeSingle());
      }
      datos(await insertar('evidencias', {
        id: d.evidencia_id, dispositivo_id: dispositivo.id, sesion_id: d.sesion_id,
        comando_id: comando?.id ?? null, tipo: d.tipo,
        ruta: rutaArchivo(dispositivo.id, d.evidencia_id, d.tipo),
        sha256: d.sha256, bytes: d.bytes, fecha: d.fecha, latitud: d.latitud, longitud: d.longitud,
      }));
      if (comando) {
        datos(await supabase.from('comandos')
          .update({ estado: 'completado', error: null, actualizado_en: new Date().toISOString() })
          .eq('id', comando.id));
      }
      return;
    }

    case 'comando_fallido':
      return datos(await supabase.from('comandos')
        .update({ estado: 'fallido', error: d.error, actualizado_en: new Date().toISOString() })
        .eq('id', d.comando_id).eq('dispositivo_id', dispositivo.id).eq('estado', 'pendiente'));
  }
}

function rutasDispositivo(supabase) {
  const r = express.Router();

  r.use(async (req, res, next) => {
    const token = (req.headers.authorization || '').replace(/^Bearer /, '');
    if (token.length < 32) return res.status(401).json({ error: 'Autenticacion requerida' });
    const dispositivo = datos(await supabase.from('dispositivos')
      .select('id,supervisor_id,limite_velocidad_kmh').eq('token_sha256', digest(token)).maybeSingle());
    if (!dispositivo) return res.status(401).json({ error: 'Token de dispositivo desconocido' });
    req.dispositivo = dispositivo;
    next();
  });

  r.post('/registros', async (req, res) => {
    const registros = req.body?.registros;
    if (!Array.isArray(registros) || !registros.length || registros.length > 100)
      return res.status(400).json({ error: 'Se requieren entre 1 y 100 registros' });
    const confirmados = [], rechazados = [];
    for (const bruto of registros) {
      let registro;
      try {
        registro = validarRegistro(bruto);
      } catch (error) {
        if (typeof bruto?.id !== 'string') return res.status(400).json({ error: 'Registro sin id' });
        rechazados.push({ id: bruto.id, motivo: error.message });
        continue;
      }
      try {
        await aplicar(supabase, req.dispositivo, registro);
        confirmados.push(registro.id);
      } catch (error) {
        // 23503 = llave foranea, 23514 = check
        if (!['23503', '23514'].includes(error.code)) throw error;
        rechazados.push({ id: registro.id, motivo: 'No cumple las restricciones de la base de datos' });
      }
    }
    res.json({ confirmados, rechazados });
  });

  r.put('/evidencias/:id', express.raw({ type: Object.keys(EXTENSION), limit: '10mb' }), async (req, res) => {
    const sha = req.headers['x-content-sha256'];
    const extension = EXTENSION[req.headers['content-type']];
    if (!UUID.test(req.params.id) || !extension || !SHA256.test(sha || '') ||
        !Buffer.isBuffer(req.body) || !req.body.length || digest(req.body) !== sha)
      return res.status(400).json({ error: 'Archivo o checksum invalido' });
    const bucket = supabase.storage.from(BUCKET);
    const ruta = `${req.dispositivo.id}/${req.params.id}.${extension}`;
    const subida = await bucket.upload(ruta, req.body,
      { contentType: req.headers['content-type'], upsert: false });
    if (subida.error) {
      // reintento: se acepta si es el mismo archivo
      const previo = datos(await bucket.download(ruta));
      if (digest(Buffer.from(await previo.arrayBuffer())) !== sha)
        return res.status(409).json({ error: 'Ya existe un archivo distinto con ese id' });
    }
    res.json({ id: req.params.id, sha256: sha, bytes: req.body.length });
  });

  r.get('/estado', async (req, res) => {
    const { id, supervisor_id, limite_velocidad_kmh } = req.dispositivo;
    await expirarComandos(supabase, [id]);
    const comandos = datos(await supabase.from('comandos').select('id,tipo,creado_en')
      .eq('dispositivo_id', id).eq('estado', 'pendiente').order('creado_en'));
    const conductores = datos(await supabase.from('conductores').select('id,nombre')
      .eq('supervisor_id', supervisor_id).eq('activo', true));
    datos(await supabase.from('dispositivos').update({ visto_en: new Date().toISOString() }).eq('id', id));
    res.json({ limite_velocidad_kmh, conductores, comandos });
  });

  return r;
}

module.exports = { rutasDispositivo, expirarComandos, datos, BUCKET };
