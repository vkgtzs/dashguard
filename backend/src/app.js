const express = require('express');
const cors = require('cors');
const { rutasDispositivo } = require('./dispositivo');
const { rutasSupervisor } = require('./supervisor');

function crearApp(supabase, { origenes = [] } = {}) {
  const app = express();

  app.use(cors({
    origin(origen, callback) {
      if (!origen) return callback(null, true); // sin navegador (Raspberry)
      try {
        const local = ['localhost', '127.0.0.1'].includes(new URL(origen).hostname);
        return callback(null, local || origenes.includes(origen));
      } catch {
        return callback(null, false);
      }
    },
  }));
  app.use(express.json({ limit: '1mb' }));

  app.get('/', (req, res) => res.json({ servicio: 'DashGuard', version: 2 }));
  app.use('/dispositivo', rutasDispositivo(supabase));
  app.use('/api', rutasSupervisor(supabase));

  app.use((req, res) => res.status(404).json({ error: 'Ruta desconocida' }));

  app.use((error, req, res, next) => {
    if (error.type === 'entity.too.large') return res.status(413).json({ error: 'Contenido demasiado grande' });
    if (error.type === 'entity.parse.failed') return res.status(400).json({ error: 'JSON invalido' });
    console.error(`${req.method} ${req.path}:`, error.message || error);
    res.status(502).json({ error: 'No se pudo completar la operacion; reintentar' });
  });

  return app;
}

module.exports = { crearApp };
