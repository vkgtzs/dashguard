const API_URL = "https://dashguard-backend.onrender.com";

let mediciones = [];
let cargando = false;
let recorridos = [];
let medicionesDisponibles = false;
let recorridosDisponibles = false;
let mapaRecorrido = null;
let capaRecorrido = null;
let limitesRecorrido = [];
let ultimoRecorridoCentrado = null;

const $ = id => document.getElementById(id);

function setText(id, texto) {
  if ($(id)) $(id).textContent = texto;
}

// Navegacion
document.querySelectorAll(".nav-item").forEach(btn => {
  btn.addEventListener("click", () => {
    showView(btn.dataset.view, btn);
  });
});

document.querySelectorAll("[data-go]").forEach(btn => {
  btn.addEventListener("click", () => {
    const target = btn.dataset.go;
    showView(
      target,
      document.querySelector(`[data-view="${target}"]`)
    );
  });
});

$("refresh-btn")?.addEventListener("click", loadMeasurements);

function showView(id, navButton) {
  if (!$(id)) return;

  document.querySelectorAll(".view").forEach(v => {
    v.classList.remove("active");
  });

  document.querySelectorAll(".nav-item").forEach(v => {
    v.classList.remove("active");
  });

  $(id).classList.add("active");
  navButton?.classList.add("active");

  const titles = {
    dashboard: "Panel de monitoreo",
    eventos: "Eventos y mediciones",
    grabaciones: "Grabaciones",
    rutas: "Ubicacion GPS",
    reportes: "Reportes",
    dispositivo: "Dispositivo"
  };

  setText("page-title", titles[id] || "DashGuard");
  if (id === 'rutas') requestAnimationFrame(() => {
    renderTripMap();
    mapaRecorrido?.invalidateSize();
    if (limitesRecorrido.length && ultimoRecorridoCentrado !== $('trip-select')?.value) fitTrip();
  });
}

// Consultar backend
async function loadMeasurements() {
  if (cargando) return;
  cargando = true;

  const button = $("refresh-btn");
  if (button) button.disabled = true;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20000);

  try {
    const response = await fetch(`${API_URL}/mediciones`, {
      cache: "no-store",
      signal: controller.signal
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    const rows = Array.isArray(data) ? data : data?.mediciones;

    if (!Array.isArray(rows)) {
      throw new Error("Respuesta de mediciones invalida");
    }

    mediciones = rows;
    medicionesDisponibles = true;
    renderAll();
    renderTripMap();

    setConnection("Backend conectado", true);
    setText("api-status", "Activo");
    setText("backend-device-status", "Activo");

    if ($("backend-device-status")) {
      $("backend-device-status").className = "status";
    }

    setText("last-update", new Date().toLocaleString("es-MX"));

  } catch (error) {
    console.error(error);

    mediciones = [];
    medicionesDisponibles = false;
    renderAll();
    renderTripMap();
    renderGPS(null, "Sin conexion");

    setConnection("Sin conexion", false);
    setText("api-status", "Error");
    setText("backend-device-status", "Sin conexion");
    setText("last-update", "Consulta fallida");

    if ($("backend-device-status")) {
      $("backend-device-status").className = "status pending";
    }

    $("recent-events").innerHTML = `
      <div class="state-message error">
        No fue posible consultar el backend.
        Revisa la conexion y API_URL.
      </div>
    `;

    $("events-table").innerHTML = `
      <tr>
        <td colspan="9" class="error">
          Error de comunicacion con el backend.
        </td>
      </tr>
    `;

    toast("No se pudo conectar con la API");

  } finally {
    clearTimeout(timeout);
    cargando = false;
    if (button) button.disabled = false;
  }
}

// Convertir numeros sin interpretar null como cero
function numeric(value) {
  if (
    value === null ||
    value === undefined ||
    typeof value === "boolean" ||
    (typeof value === "string" && !value.trim())
  ) {
    return null;
  }

  if (typeof value !== "number" && typeof value !== "string") {
    return null;
  }

  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function normalize(m, index) {
  m = m && typeof m === "object" ? m : {};

  const latitud = numeric(m.latitud);
  const longitud = numeric(m.longitud);

  const gpsValido =
    m.gps_valido === true &&
    latitud !== null &&
    longitud !== null &&
    latitud >= -90 &&
    latitud <= 90 &&
    longitud >= -180 &&
    longitud <= 180;

  return {
    id: m.id ?? index + 1,
    variable: m.variable ?? m.tipo ?? "medicion",
    valor: numeric(m.valor ?? m.value),
    unidad: m.unidad ?? m.unit ?? "",
    fecha:
      m.fecha_hora ??
      m.fecha ??
      m.timestamp ??
      m.created_at ??
      "",
    gpsValido,
    latitud,
    longitud,
    satelites: numeric(m.satelites),
    hdop: numeric(m.hdop)
  };
}

// Mostrar mediciones
function renderAll() {
  // Tu backend devuelve los registros por ID ascendente.
  const rows = mediciones.map(normalize);

  setText("event-count", rows.length);
  setText("report-total", rows.length);

  for (const id of [
    "report-max",
    "report-avg",
    "report-max-unit",
    "report-avg-unit"
  ]) {
    setText(id, "—");
  }

  if (!rows.length) {
    setText("latest-value", "—");
    setText("latest-unit", "Sin datos");

    $("recent-events").innerHTML = `
      <div class="state-message">
        Todavia no hay mediciones registradas.
      </div>
    `;

    $("events-table").innerHTML = `
      <tr><td colspan="9">No hay datos almacenados.</td></tr>
    `;

    renderGPS(null);
    return;
  }

  const latest = rows[rows.length - 1];

  setText("latest-value", formatNumber(latest.valor));
  setText(
    "latest-unit",
    `${latest.variable}${latest.unidad ? " · " + latest.unidad : ""}`
  );

  renderGPS(latest);

  $("recent-events").innerHTML = rows
    .slice(-5)
    .reverse()
    .map(r => `
      <div class="event-row">
        <div class="event-id">#${escapeHtml(r.id)}</div>

        <div>
          <p>${escapeHtml(r.variable)}</p>
          <small>${escapeHtml(formatDate(r.fecha))}</small>
        </div>

        <div class="event-value">
          <strong>${formatNumber(r.valor)}</strong>
          <small>${escapeHtml(r.unidad)}</small>
        </div>
      </div>
    `)
    .join("");

  $("events-table").innerHTML = rows
    .slice()
    .reverse()
    .map(r => `
      <tr>
        <td>#${escapeHtml(r.id)}</td>
        <td>${escapeHtml(r.variable)}</td>
        <td>${formatNumber(r.valor)}</td>
        <td>${escapeHtml(r.unidad || "—")}</td>
        <td>${escapeHtml(formatDate(r.fecha))}</td>

        <td>
          <span class="status ${r.gpsValido ? "" : "pending"}">
            ${r.gpsValido ? "GPS valido" : "Sin ubicacion"}
          </span>
        </td>

        <td>${r.gpsValido ? r.latitud.toFixed(6) : "—"}</td>
        <td>${r.gpsValido ? r.longitud.toFixed(6) : "—"}</td>

        <td>${
          r.gpsValido && Number.isInteger(r.satelites)
            ? r.satelites
            : "—"
        }</td>
      </tr>
    `)
    .join("");

  // Calcular estadisticas sin mezclar variables o unidades.
  const values = rows
    .filter(r =>
      r.variable === latest.variable &&
      r.unidad === latest.unidad
    )
    .map(r => r.valor)
    .filter(n => n !== null && Number.isFinite(n));

  if (values.length) {
    const max = values.reduce(
      (a, b) => Math.max(a, b),
      -Infinity
    );

    const avg =
      values.reduce((a, b) => a + b, 0) / values.length;

    setText("report-max", formatNumber(max));
    setText("report-avg", formatNumber(avg));

    const etiqueta =
      `${latest.variable} · ${latest.unidad || "valor"}`;

    setText("report-max-unit", etiqueta);
    setText("report-avg-unit", etiqueta);
  }
}

// Mostrar GPS de la ultima medicion
function renderGPS(row, override) {
  const link = $("gps-map-link");

  // Limpiar la ubicacion anterior.
  if (link) {
    link.hidden = true;
    link.style.display = "none";
    link.removeAttribute("href");
  }

  setText("gps-latitude", "—");
  setText("gps-longitude", "—");
  setText("gps-satellites", "—");
  setText("gps-hdop", "HDOP: —");

  setText(
    "gps-timestamp",
    row
      ? `Medicion: ${formatDate(row.fecha)}`
      : "Sin mediciones disponibles"
  );

  let estado =
    override || (row ? "Sin ubicacion" : "Sin datos");

  if (row?.gpsValido && !override) {
    const timestamp = Date.parse(row.fecha);

    const antigua =
      !Number.isFinite(timestamp) ||
      Date.now() - timestamp > 60000;

    estado = antigua
      ? "Ubicacion guardada"
      : "Ubicacion recibida";

    setText("gps-latitude", row.latitud.toFixed(6));
    setText("gps-longitude", row.longitud.toFixed(6));

    setText(
      "gps-satellites",
      Number.isInteger(row.satelites) ? row.satelites : "—"
    );

    setText("gps-hdop", `HDOP: ${formatNumber(row.hdop)}`);

    if (link) {
      link.href =
        `https://www.google.com/maps?q=` +
        `${row.latitud.toFixed(6)},${row.longitud.toFixed(6)}`;

      link.hidden = false;
      link.style.removeProperty("display");
    }
  }

  setText("gps-status", estado);
  setText("gps-device-status", estado);

  if ($("gps-device-status")) {
    $("gps-device-status").className =
      row?.gpsValido && !override
        ? "status testing"
        : "status pending";
  }
}

function setConnection(text, ok) {
  setText("connection-text", text);
  $("connection-badge").style.opacity = ok ? "1" : ".8";
}

function formatNumber(n) {
  return n !== null && Number.isFinite(n)
    ? n.toFixed(2)
    : "—";
}

function formatDate(value) {
  if (!value) return "Fecha asignada por backend";

  const d = new Date(value);

  return Number.isNaN(d.getTime())
    ? String(value)
    : d.toLocaleString("es-MX");
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  })[c]);
}

function toast(message) {
  if (!$("toast")) return;

  setText("toast", message);
  $("toast").classList.add("show");

  setTimeout(() => {
    $("toast").classList.remove("show");
  }, 2600);
}

loadMeasurements();
setInterval(loadMeasurements, 5000);

// El navegador consulta; los botones fisicos controlan el recorrido.
let consultandoRecorridos = false;
async function loadTrips() {
  if (consultandoRecorridos || !$('trips-table')) return;
  consultandoRecorridos = true;
  const button = $('trips-refresh');
  if (button) button.disabled = true;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 20000);
  try {
    const response = await fetch(`${API_URL}/recorridos?device_id=dashguard-001`, {
      cache:'no-store', signal:controller.signal
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (!Array.isArray(data.recorridos)) throw new Error('Formato de recorridos invalido');
    recorridos = data.recorridos;
    recorridosDisponibles = true;
    updateTripSelector();
    renderTripMap();
    const activo = data.recorridos.find(r => r.estado === 'activo');
    setText('trip-status', activo ? 'Recorrido activo: pulsa GPIO26 para finalizar.' : 'Sin recorrido activo: pulsa GPIO25 para iniciar.');
    $('trips-table').innerHTML = data.recorridos.length ? data.recorridos.map(r => `
      <tr><td>${escapeHtml(r.estado)}</td>
      <td>${escapeHtml(formatDate(r.inicio_fecha))}</td>
      <td>${tripPoint(r.inicio_latitud,r.inicio_longitud)}</td>
      <td>${r.final_fecha ? escapeHtml(formatDate(r.final_fecha)) : 'Pendiente'}</td>
      <td>${tripPoint(r.final_latitud,r.final_longitud)}</td></tr>
    `).join('') : '<tr><td colspan="5">Todavia no hay recorridos.</td></tr>';
  } catch (error) {
    console.error(error);
    recorridosDisponibles = false;
    renderTripMap();
    setText('trip-status','No se pudo consultar recorridos. Revisa el backend y la migracion SQL.');
    $('trips-table').innerHTML = '<tr><td colspan="5">Estado desconocido: consulta fallida.</td></tr>';
  } finally {
    clearTimeout(timer);consultandoRecorridos=false;
    if (button) button.disabled=false;
  }
}
function tripPoint(lat, lon) {
  lat=numeric(lat);lon=numeric(lon);
  if (lat===null || lon===null || lat < -90 || lat > 90 || lon < -180 || lon > 180) return '—';
  const coords=`${lat.toFixed(6)},${lon.toFixed(6)}`;
  return `<a href="https://www.google.com/maps?q=${coords}" target="_blank" rel="noopener noreferrer">${coords}</a>`;
}
$('trips-refresh')?.addEventListener('click',loadTrips);
loadTrips();
setInterval(loadTrips,5000);


function updateTripSelector() {
  const select=$('trip-select');
  if (!select) return;
  const anterior=select.value;
  select.replaceChildren();
  for (const trip of recorridos) {
    const option=document.createElement('option');
    option.value=String(trip.id);
    option.textContent=`${formatDate(trip.inicio_fecha)} · ${trip.estado}`;
    select.append(option);
  }
  select.disabled=!recorridos.length;
  if (!recorridos.length) {
    const option=document.createElement('option');
    option.value='';option.textContent='Sin recorridos guardados';select.append(option);
  } else if (recorridos.some(t=>String(t.id)===anterior)) select.value=anterior;
  else select.value=String((recorridos.find(t=>t.estado==='activo') || recorridos[0]).id);
}
function validTripPoint(lat,lon) {
  lat=numeric(lat);lon=numeric(lon);
  return lat!==null && lon!==null && lat>=-90 && lat<=90 && lon>=-180 && lon<=180 ? [lat,lon] : null;
}
function tripMeasurementTime(m) {
  const value=m.fecha_hora ?? m.fecha ?? m.timestamp ?? m.created_at;
  return value ? Date.parse(value) : NaN;
}
// The endpoint orders measurements by ascending ID. Only same-trip/device rows enter.
function buildTripGeometry(trip, measurements) {
  const start=validTripPoint(trip.inicio_latitud,trip.inicio_longitud);
  const end=trip.estado==='finalizado' ? validTripPoint(trip.final_latitud,trip.final_longitud) : null;
  const rows=measurements.filter(m=>m && String(m.recorrido_id)===String(trip.id) && m.device_id===trip.device_id);
  const segments=[];const points=[];
  let segment=start ? [start] : [];
  let previousTime=Date.parse(trip.inicio_fecha);
  let breaks=0;
  function closeSegment() {if(segment.length>1) segments.push(segment);segment=[];}
  for(const row of rows) {
    const coord=row.gps_valido===true ? validTripPoint(row.latitud,row.longitud) : null;
    const time=tripMeasurementTime(row);
    if(!coord) {closeSegment();previousTime=NaN;breaks++;continue;}
    if(Number.isFinite(time) && Number.isFinite(previousTime) && (time-previousTime>60000 || time<previousTime)) {
      closeSegment();breaks++;
    }
    points.push({coord,row});segment.push(coord);previousTime=time;
  }
  // With no intermediate samples, endpoints are markers only.
  if(end && points.length && segment.length) {
    const endTime=Date.parse(trip.final_fecha);
    if(Number.isFinite(endTime) && Number.isFinite(previousTime) && (endTime-previousTime>60000 || endTime<previousTime)) {
      closeSegment();breaks++;
    } else segment.push(end);
  }
  closeSegment();
  return {start,end,points,segments,breaks};
}
function ensureTripMap() {
  if(mapaRecorrido) return true;
  if(typeof L==='undefined') {
    setText('trip-map-status','No se pudo cargar el mapa. Revisa tu conexión y recarga la página.');return false;
  }
  if(!$('rutas')?.classList.contains('active')) return false;
  mapaRecorrido=L.map('trip-map').setView([23.6,-102.5],5);
  const tiles=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom:19, attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }).addTo(mapaRecorrido);
  tiles.on('tileerror',()=>setText('trip-tile-status','No se pudieron cargar algunas imágenes del mapa. Los puntos GPS siguen disponibles.'));
  capaRecorrido=L.layerGroup().addTo(mapaRecorrido);
  return true;
}
function mapPoint(coord,color,label) {
  if (!coord) return;
  // Text node prevents backend values from being interpreted as popup HTML.
  const popup=document.createElement('div');popup.textContent=label;
  L.circleMarker(coord,{radius:8,color:'#ffffff',weight:2,fillColor:color,fillOpacity:1})
    .bindPopup(popup).addTo(capaRecorrido);
}
function renderTripMap() {
  if(!$('trip-map')) return;
  capaRecorrido?.clearLayers();
  limitesRecorrido=[];
  setText('trip-start-time','—');setText('trip-end-time','—');setText('trip-point-count','0');
  if(!recorridosDisponibles || !medicionesDisponibles) {
    setText('trip-map-status','Esperando una consulta válida de recorridos y mediciones...');return;
  }
  const trip=recorridos.find(t=>String(t.id)===$('trip-select')?.value);
  if(!trip) {setText('trip-map-status','Inicia un recorrido con GPIO25 para registrar sus puntos.');return;}
  const geo=buildTripGeometry(trip,mediciones);
  setText('trip-start-time',formatDate(trip.inicio_fecha));
  setText('trip-end-time',trip.final_fecha ? formatDate(trip.final_fecha) : 'En curso');
  setText('trip-point-count',geo.points.length);
  const message=geo.points.length
    ? `${geo.points.length} mediciones con GPS válido · ${trip.estado}${geo.breaks ? ' · hay tramos sin datos continuos' : ''}`
    : 'Solo puntos de inicio/final disponibles. Esperando mediciones GPS asociadas para dibujar el trayecto.';
  setText('trip-map-status',message);
  if(!ensureTripMap()) return;
  for(const segment of geo.segments) L.polyline(segment,{color:'#3388ff',weight:5,opacity:0.9}).addTo(capaRecorrido);
  for(const point of geo.points) {
    const popup=document.createElement('div');
    popup.textContent=`Medición #${point.row.id ?? '—'} · ${formatDate(point.row.fecha_hora ?? point.row.fecha ?? point.row.timestamp ?? point.row.created_at)} · Aceleración: ${formatNumber(numeric(point.row.valor))} ${point.row.unidad ?? ''}`;
    L.circleMarker(point.coord,{radius:4,color:'#3388ff',weight:1,fillOpacity:0.75})
      .bindPopup(popup).addTo(capaRecorrido);
  }
  mapPoint(geo.start,'#25a55f',`Inicio: ${formatDate(trip.inicio_fecha)}`);
  mapPoint(geo.end,'#e05050',`Final: ${formatDate(trip.final_fecha)}`);
  limitesRecorrido=[geo.start,...geo.points.map(p=>p.coord),geo.end].filter(Boolean);
  if(ultimoRecorridoCentrado!==String(trip.id)) fitTrip();
}
function fitTrip() {
  if(!mapaRecorrido || !limitesRecorrido.length) return;
  mapaRecorrido.invalidateSize();
  mapaRecorrido.fitBounds(L.latLngBounds(limitesRecorrido),{padding:[28,28],maxZoom:17});
  ultimoRecorridoCentrado=$('trip-select')?.value;
}
$('trip-select')?.addEventListener('change',()=>{ultimoRecorridoCentrado=null;renderTripMap();});
$('trip-fit')?.addEventListener('click',fitTrip);
