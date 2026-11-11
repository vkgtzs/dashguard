require('dotenv').config({ quiet: true });
const { createClient } = require('@supabase/supabase-js');
const { crearApp } = require('./app');

const { SUPABASE_URL, SUPABASE_KEY, ORIGENES_APP = '', PORT = 3000 } = process.env;
if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Faltan SUPABASE_URL y SUPABASE_KEY (ver .env.example)');
  process.exit(1);
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY, { auth: { persistSession: false } });
const origenes = ORIGENES_APP.split(',').map(o => o.trim()).filter(Boolean);

crearApp(supabase, { origenes }).listen(PORT, () => console.log(`DashGuard backend en el puerto ${PORT}`));
