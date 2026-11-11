'use strict';
(function (raiz) {
  const SALTO_MAXIMO_MS = 30000; // huecos de GPS mayores no se unen

  function preparar(puntos) {
    const tramos = [];
    let tramo = [], anterior = null;
    for (const p of puntos) {
      const t = Date.parse(p.fecha);
      if (anterior !== null && (!(t > anterior) || t - anterior > SALTO_MAXIMO_MS)) {
        if (tramo.length) tramos.push(tramo);
        tramo = [];
      }
      tramo.push([p.latitud, p.longitud]);
      anterior = t;
    }
    if (tramo.length) tramos.push(tramo);
    return tramos;
  }

  function crear(contenedor) {
    let mapa = null, capas = null;

    function limpiar() {
      if (capas) capas.clearLayers();
      contenedor.hidden = true;
    }

    function mostrar(puntos, limite_kmh) {
      limpiar();
      if (!puntos.length || !raiz.L) return;
      contenedor.hidden = false;
      if (!mapa) {
        mapa = raiz.L.map(contenedor, { preferCanvas: true });
        raiz.L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
          maxZoom: 19,
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        }).addTo(mapa);
        raiz.L.control.scale({ imperial: false }).addTo(mapa);
        capas = raiz.L.layerGroup().addTo(mapa);
      }
      for (const tramo of preparar(puntos)) {
        if (tramo.length > 1) raiz.L.polyline(tramo, { color: '#175fa6', weight: 4, opacity: 0.7 }).addTo(capas);
      }
      const etiqueta = (p, titulo) => {
        const texto = document.createElement('p');
        const hora = new Date(p.fecha).toLocaleTimeString();
        const velocidad = p.velocidad_kmh == null ? 'velocidad no disponible' : p.velocidad_kmh.toFixed(0) + ' km/h';
        texto.textContent = `${titulo} · ${hora} · ${velocidad}`;
        return texto;
      };
      if (Number.isFinite(limite_kmh)) {
        for (const p of puntos) {
          if (p.velocidad_kmh > limite_kmh) {
            raiz.L.circleMarker([p.latitud, p.longitud], { radius: 5, color: '#b3261e', weight: 1, fillColor: '#e5484d', fillOpacity: 0.9 })
              .bindPopup(() => etiqueta(p, 'Exceso de velocidad')).addTo(capas);
          }
        }
      }
      const extremos = [[puntos[0], '#16834a', 'Inicio'], [puntos.at(-1), '#c96816', 'Fin']];
      for (const [p, color, titulo] of extremos) {
        raiz.L.circleMarker([p.latitud, p.longitud], { radius: 8, color, weight: 3, fillOpacity: 0.2 })
          .bindPopup(() => etiqueta(p, titulo)).addTo(capas);
      }
      mapa.invalidateSize();
      mapa.fitBounds(raiz.L.latLngBounds(puntos.map(p => [p.latitud, p.longitud])), { padding: [25, 25], maxZoom: 17 });
    }

    return { mostrar, limpiar };
  }

  const api = { preparar, crear };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else raiz.DashGuardMapa = api;
})(globalThis);
