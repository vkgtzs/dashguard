// npm test (usa un Supabase simulado, sin red)
const test = require('node:test');
const assert = require('node:assert/strict');
const { validarRegistro } = require('../src/validar');
const { crearApp } = require('../src/app');

const ID = '11111111-2222-4333-8444-555555555555';
const SESION = 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee';
const FECHA = '2026-11-11T18:30:00Z';
const punto = (extra = {}) => ({
  id: ID, tipo: 'punto',
  datos: { sesion_id: SESION, fecha: FECHA, latitud: 19.43, longitud: -99.13, velocidad_kmh: 42.5, ...extra },
});

test('acepta un punto valido y completa los campos opcionales', () => {
  const r = validarRegistro(punto());
  assert.equal(r.datos.velocidad_kmh, 42.5);
  assert.equal(r.datos.satelites, null);
});

test('rechaza coordenadas, fechas y tipos invalidos', () => {
  assert.throws(() => validarRegistro(punto({ latitud: 91 })), /latitud/);
  assert.throws(() => validarRegistro(punto({ fecha: '11/11/2026' })), /fecha/);
  assert.throws(() => validarRegistro(punto({ sesion_id: 'x' })), /sesion_id/);
  assert.throws(() => validarRegistro({ id: ID, tipo: 'otro', datos: {} }), /desconocido/);
});

test('descarta campos que el dispositivo no debe fijar', () => {
  const r = validarRegistro(punto({ dispositivo_id: 'otro-equipo' }));
  assert.equal('dispositivo_id' in r.datos, false);
});

test('verificacion: conductor solo cuando esta autorizado', () => {
  const v = datos => validarRegistro({ id: ID, tipo: 'verificacion', datos: { sesion_id: SESION, ...datos } });
  assert.equal(v({ resultado: 'no_concluyente' }).datos.conductor_id, null);
  assert.equal(v({ resultado: 'autorizado', conductor_id: ID }).datos.conductor_id, ID);
  assert.throws(() => v({ resultado: 'autorizado' }), /conductor_id/);
  assert.throws(() => v({ resultado: 'no_reconocido', conductor_id: ID }), /conductor_id/);
});

function supabaseSimulado(resultado, escrituras = []) {
  const cadena = tabla => {
    const p = new Proxy(function () {}, {
      get: (_, nombre) => {
        if (nombre === 'then') return resolver => resolver(resultado);
        return (...args) => {
          if (['upsert', 'update', 'insert', 'delete'].includes(nombre)) escrituras.push({ tabla, nombre, args });
          return p;
        };
      },
    });
    return p;
  };
  return {
    from: cadena,
    auth: { getUser: async () => ({ data: { user: null }, error: { message: 'token invalido' } }) },
    storage: { from: () => ({}) },
  };
}

async function conServidor(supabase, prueba) {
  const servidor = crearApp(supabase).listen(0, '127.0.0.1');
  await new Promise(listo => servidor.once('listening', listo));
  try {
    await prueba(`http://127.0.0.1:${servidor.address().port}`);
  } finally {
    servidor.close();
  }
}

test('sin credenciales no se entra a ninguna ruta', async () => {
  await conServidor(supabaseSimulado({ data: null, error: null }), async base => {
    assert.equal((await fetch(base + '/')).status, 200);
    assert.equal((await fetch(base + '/dispositivo/estado')).status, 401);
    assert.equal((await fetch(base + '/api/sesiones')).status, 401);
    const desconocido = await fetch(base + '/dispositivo/estado', { headers: { Authorization: 'Bearer ' + 'x'.repeat(40) } });
    assert.equal(desconocido.status, 401);
    const supervisor = await fetch(base + '/api/sesiones', { headers: { Authorization: 'Bearer falso' } });
    assert.equal(supervisor.status, 401);
  });
});

test('un lote confirma lo valido y aparta lo invalido', async () => {
  const escrituras = [];
  const dispositivo = { id: 'pi-1', supervisor_id: 'u-1', limite_velocidad_kmh: 80 };
  await conServidor(supabaseSimulado({ data: dispositivo, error: null }, escrituras), async base => {
    const malo = { id: SESION, tipo: 'punto', datos: { sesion_id: SESION, fecha: FECHA, latitud: 200, longitud: 0 } };
    const r = await fetch(base + '/dispositivo/registros', {
      method: 'POST',
      headers: { Authorization: 'Bearer ' + 't'.repeat(40), 'Content-Type': 'application/json' },
      body: JSON.stringify({ registros: [punto({ dispositivo_id: 'otro-equipo' }), malo] }),
    });
    assert.equal(r.status, 200);
    const cuerpo = await r.json();
    assert.deepEqual(cuerpo.confirmados, [ID]);
    assert.equal(cuerpo.rechazados[0].id, SESION);
    assert.equal(escrituras.length, 1);
    assert.equal(escrituras[0].tabla, 'puntos');
    assert.equal(escrituras[0].args[0].dispositivo_id, 'pi-1');
    assert.equal(escrituras[0].args[0].id, ID);
  });
});

test('un fallo de la base responde 502 para que el dispositivo reintente', async () => {
  let llamadas = 0;
  const supabase = supabaseSimulado(null);
  const dispositivo = { id: 'pi-1', supervisor_id: 'u-1', limite_velocidad_kmh: 80 };
  supabase.from = () => {
    const resultado = llamadas++ === 0 ? { data: dispositivo, error: null } : { data: null, error: { code: '08006', message: 'sin conexion' } };
    return supabaseSimulado(resultado).from('x');
  };
  await conServidor(supabase, async base => {
    const r = await fetch(base + '/dispositivo/registros', {
      method: 'POST',
      headers: { Authorization: 'Bearer ' + 't'.repeat(40), 'Content-Type': 'application/json' },
      body: JSON.stringify({ registros: [punto()] }),
    });
    assert.equal(r.status, 502);
  });
});
