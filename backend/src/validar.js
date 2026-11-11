// Validación de los registros que envía el dispositivo.

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const SHA256 = /^[a-f0-9]{64}$/;
const FECHA = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,3})?Z$/;

function uuid(valor, nombre) {
  if (typeof valor !== 'string' || !UUID.test(valor)) throw Error(`${nombre} debe ser un UUID`);
  return valor;
}
const uuidOpcional = (valor, nombre) => (valor == null ? null : uuid(valor, nombre));

function fecha(valor) {
  if (typeof valor !== 'string' || !FECHA.test(valor) || Number.isNaN(Date.parse(valor)))
    throw Error('fecha debe ser ISO UTC, por ejemplo 2026-11-11T18:30:00Z');
  return valor;
}

function numero(valor, nombre, minimo, maximo) {
  if (typeof valor !== 'number' || !Number.isFinite(valor) || valor < minimo || valor > maximo)
    throw Error(`${nombre} fuera de rango`);
  return valor;
}
const numeroOpcional = (valor, nombre, minimo, maximo) =>
  (valor == null ? null : numero(valor, nombre, minimo, maximo));

function posicionOpcional(d) {
  if (d.latitud == null && d.longitud == null) return { latitud: null, longitud: null };
  return {
    latitud: numero(d.latitud, 'latitud', -90, 90),
    longitud: numero(d.longitud, 'longitud', -180, 180),
  };
}

const validadores = {
  sesion_inicio: d => ({ sesion_id: uuid(d.sesion_id, 'sesion_id'), fecha: fecha(d.fecha) }),

  verificacion: d => {
    if (!['autorizado', 'no_reconocido', 'no_concluyente'].includes(d.resultado))
      throw Error('resultado de verificacion desconocido');
    const conductor = uuidOpcional(d.conductor_id, 'conductor_id');
    if ((d.resultado === 'autorizado') !== (conductor !== null))
      throw Error('conductor_id se envia solo cuando el resultado es autorizado');
    return { sesion_id: uuid(d.sesion_id, 'sesion_id'), resultado: d.resultado, conductor_id: conductor };
  },

  sesion_fin: d => ({
    sesion_id: uuid(d.sesion_id, 'sesion_id'),
    fecha: fecha(d.fecha),
    distancia_m: numero(d.distancia_m, 'distancia_m', 0, 5e6),
  }),

  punto: d => ({
    sesion_id: uuid(d.sesion_id, 'sesion_id'),
    fecha: fecha(d.fecha),
    latitud: numero(d.latitud, 'latitud', -90, 90),
    longitud: numero(d.longitud, 'longitud', -180, 180),
    velocidad_kmh: numeroOpcional(d.velocidad_kmh, 'velocidad_kmh', 0, 400),
    satelites: numeroOpcional(d.satelites, 'satelites', 0, 99),
    hdop: numeroOpcional(d.hdop, 'hdop', 0, 100),
  }),

  alerta: d => {
    if (!['conductor_no_reconocido', 'exceso_velocidad'].includes(d.tipo))
      throw Error('tipo de alerta desconocido');
    const detalle = d.detalle ?? {};
    if (typeof detalle !== 'object' || Array.isArray(detalle) || JSON.stringify(detalle).length > 2000)
      throw Error('detalle invalido');
    return {
      sesion_id: uuidOpcional(d.sesion_id, 'sesion_id'),
      tipo: d.tipo,
      fecha: fecha(d.fecha),
      ...posicionOpcional(d),
      detalle,
    };
  },

  evidencia: d => {
    if (!['foto', 'video'].includes(d.tipo)) throw Error('tipo de evidencia desconocido');
    if (typeof d.sha256 !== 'string' || !SHA256.test(d.sha256)) throw Error('sha256 invalido');
    if (!Number.isInteger(d.bytes) || d.bytes <= 0) throw Error('bytes invalido');
    return {
      evidencia_id: uuid(d.evidencia_id, 'evidencia_id'),
      tipo: d.tipo,
      sesion_id: uuidOpcional(d.sesion_id, 'sesion_id'),
      comando_id: uuidOpcional(d.comando_id, 'comando_id'),
      fecha: fecha(d.fecha),
      ...posicionOpcional(d),
      sha256: d.sha256,
      bytes: d.bytes,
    };
  },

  comando_fallido: d => ({
    comando_id: uuid(d.comando_id, 'comando_id'),
    error: typeof d.error === 'string' ? d.error.slice(0, 200) : 'sin detalle',
  }),
};

function validarRegistro(registro) {
  if (!registro || typeof registro !== 'object') throw Error('Registro invalido');
  const validar = validadores[registro.tipo];
  if (!validar) throw Error('Tipo de registro desconocido');
  if (!registro.datos || typeof registro.datos !== 'object' || Array.isArray(registro.datos))
    throw Error('datos debe ser un objeto');
  return { id: uuid(registro.id, 'id'), tipo: registro.tipo, datos: validar(registro.datos) };
}

module.exports = { validarRegistro, UUID, SHA256 };
