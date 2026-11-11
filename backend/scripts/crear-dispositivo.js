// Da de alta una Raspberry y la asigna a un supervisor ya registrado en Supabase Auth.
//
//   node scripts/crear-dispositivo.js <id> <correo-del-supervisor> "<nombre>" <url-del-backend>
//   node scripts/crear-dispositivo.js dashguard-pi-001 ana@ejemplo.com "Auto familiar" https://mi-backend.onrender.com
//
require('dotenv').config({ path: require('node:path').join(__dirname, '../.env'), quiet: true });
const crypto = require('node:crypto');
const fs = require('node:fs');
const { createClient } = require('@supabase/supabase-js');

async function main() {
  const [id, correo, nombre, backend] = process.argv.slice(2);
  if (!/^[a-z0-9-]{1,80}$/.test(id || '') || !correo || !nombre || !/^https:\/\//.test(backend || ''))
    throw Error('Uso: node scripts/crear-dispositivo.js <id> <correo> "<nombre>" <https://backend>');

  const supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_KEY,
    { auth: { persistSession: false } });
  const usuarios = await supabase.auth.admin.listUsers({ perPage: 1000 });
  if (usuarios.error) throw usuarios.error;
  const supervisor = usuarios.data.users.find(u => u.email?.toLowerCase() === correo.toLowerCase());
  if (!supervisor) throw Error('No existe un usuario con ese correo en Supabase Auth');

  const token = crypto.randomBytes(32).toString('base64url');
  const archivo = 'dispositivo.json';
  fs.writeFileSync(archivo, JSON.stringify({ backend, dispositivo_id: id, token }, null, 2),
    { flag: 'wx', mode: 0o600 });

  const { error } = await supabase.from('dispositivos').insert({
    id, nombre, supervisor_id: supervisor.id,
    token_sha256: crypto.createHash('sha256').update(token).digest('hex'),
  });
  if (error) {
    fs.unlinkSync(archivo);
    throw error;
  }
  console.log(`Dispositivo ${id} creado. Copia ${archivo} a ~/dashguard/config/ en la Raspberry y borralo de aqui.`);
}

main().catch(error => {
  console.error('ERROR:', error.message);
  process.exitCode = 1;
});
