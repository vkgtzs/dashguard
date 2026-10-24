# Loop acotado con telemetria

Instalar dashguard_local.py actualizado, video_loop_prueba.py y retencion.py
en el home de la Raspberry. Detener captura antes de reemplazar su programa.
Conservar respaldo del registrador anterior y de SQLite con ambos servicios
detenidos. Mantener sincronizacion pausada durante la prueba.

El registrador agrega boot_id sin modificar filas anteriores. Esas filas
historicas no se vinculan usando monotonic_s porque podria pertenecer a otro
arranque. Cada clip nuevo tiene UUID, MP4 y JSON con muestras capturadas durante
la ventana del proceso rpicam-vid del mismo arranque. Incluye ausencia de GPS
tal como se registro. No inventa ubicacion. No son overlays ni precision por
fotograma: la ventana incluye configuracion/cierre de camara y la IMU es de 1 Hz.

Ejecutar captura (mantener sensor inmovil durante calibracion) y despues:

```bash
python3 ~/video_loop_prueba.py --clips 9
```

Graba nueve clips de diez segundos solicitados; el tiempo total sera mayor
por inicializacion y conversion. Reabre camara entre clips: existen huecos.
La grabacion continua con rpicam --segment fue probada previamente pero aun
no integrada con estos metadatos. No llamar a esto loop continuo de produccion.

Solo usa ~/dashguard/videos/loop_prueba. Conserva seis clips no protegidos;
los protegidos quedan fuera del limite. No limita el total de evidencia
protegida. Detiene antes de grabar si quedan menos de 512 MiB libres. Los
parciales de interrupciones se conservan; no hay recuperacion automatica.

Para proteger evidencia, detener este programa y luego marcar en SQLite:
`UPDATE videos_locales SET protegido=1 WHERE id='UUID_DEL_VIDEO';`
No existe deteccion automatica de eventos. La tabla video_muestras conserva
las referencias de TODOS los videos retenidos, protegidos o no. Los JSON
incluyen copia de telemetria para que al exportar no dependan solo de SQLite.

Despues de cada clip rota los videos y limpia muestras con captura Y confirmacion
de mas de siete dias. Nunca elimina pendientes, sin cola o asociadas a videos
retenidos. Se eliminan las filas de cola confirmadas correspondientes en la
misma transaccion. Fuera del loop no hay timer de limpieza instalado.

```bash
python3 ~/retencion.py
python3 ~/retencion.py --aplicar
```

Primer comando solo cuenta candidatas. SQLite reutiliza espacio interno; no
se fuerza VACUUM con captura activa. Los respaldos SQLite no se eliminan y
deben administrarse aparte. No se modifica Supabase ni se suben los videos.
Pendientes y protegidos pueden crecer: no es un limite global de almacenamiento.

Validacion en PC: sintaxis y prueba de retencion con SQLite en memoria.
Falta prueba real de rotacion, reproduccion y telemetria concurrente en Pi.
