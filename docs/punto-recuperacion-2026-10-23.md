# Punto de recuperacion: video, GPS e IMU, 23 de octubre de 2026

Etiqueta Git: `punto-recuperacion-2026-10-23`. Respaldo del codigo disponible
en Windows, documentado con resultados de terminal y reproduccion confirmada
por la usuaria. No es una imagen de microSD ni copia de datos o esquema completo.

## Ensayo integrado completado

Raspberry Pi Zero 2 W, Raspbian 13 de 32 bits, Python 3.13.5, camara OV5647,
MPU6050 por I2C y NEO-6M por UART. Alimentacion/cableado de laboratorio.

Comando del ensayo final (servicio temporal de usuario):

```bash
systemd-run --user --unit=dashguard-video-15min-c --collect \
  /usr/bin/python3 -u /home/vkgtzs/video_espacio.py \
  --duracion 900 --segmento 10 --limite-mib 30
```

- Captura H264 1280x720, 15fps nominales, 2 Mbps, una instancia de rpicam.
- Segmentos solicitados de 10 s, cortes observados de 150/165 frames segun
  cuadros clave. No se garantiza duracion exacta de diez segundos por clip.
- Frames, PTS y SensorTimestamp validados por segmento; medidas vinculadas
  con boottime_ns y boot_id. GPS valido y 10/11 muestras en segmentos completos
  mostrados. No hay auditoria automatica exhaustiva de todo el ensayo.
- Rotacion por espacio activa. Presupuesto blando 30 MiB para loop_espacio,
  incluido trabajo temporal; ocupacion observada aproximadamente 15-17 MiB.
- Lectura cerca de minuto 13: 57.5 C y throttled=0x0. No es temperatura maxima
  continua registrada ni garantiza condiciones de instalacion dentro del auto.
- Limite de captura alcanzado a las 23:15:10 hora local. Procesamiento final
  completo a las 23:15:20, mensaje Grabacion terminada. Ultimo segmento mostrado
  con 126 frames, nueve muestras y nueve GPS validas.
- Servicio temporal desaparecio tras terminar por --collect. Sin procesos de
  grabacion restantes en la consulta mostrada.

## Exportacion verificada

`python3 ~/exportar_video.py` unio la ultima secuencia retenida:

- Cinco segmentos, 786 frames, 52.40 segundos.
- recorrido.mp4 reproducido correctamente por la usuaria en Windows.
- recorrido.json con segmentos, tiempos originales y muestras; ubicacion de
  mediciones en reproduccion aproximada al frame precedente, sin interpolacion.
- Originales conservados; exportacion fuera de cuota, ocupa espacio adicional.
- No conserva todos los quince minutos: clips antiguos se eliminaron al rotar.

Identificador de evidencia local (no archivo publicado):
`exportacion_7cfa112d-116b-4198-895b-63d11756f6d7`.

## Incidentes anteriores al ensayo final

Dos ensayos previos terminaron con bloques IMU en cero y registro PWR_MGMT_1
0x40 (SLEEP), aunque WHO_AM_I respondia 0x68. Escritura 0x00 restauro lecturas.
La usuaria identifico jumper desprendido y lo reemplazo antes del ensayo final.
Una interrupcion electrica es compatible con reinicio del sensor; no hubo
medicion electrica que establezca causalidad completa. No ocultar reincidencias.
Video continuaba mientras el registrador descartaba muestras de IMU y, por su
diseno actual, tampoco guardaba el GPS en esas iteraciones. Pendiente desacoplar
registro GPS del estado IMU y mejorar aviso/recuperacion del sensor.

## Versiones clave

- raspberry/dashguard_local.py: calibracion, GPS, SQLite, boot_id y boottime_ns.
- raspberry/video_espacio.py: procesamiento concurrente, cuota, proteccion manual.
- raspberry/exportar_video.py: concatenacion validada y telemetria exportada.
- raspberry/retencion.py: solo captura Y confirmacion >7 dias y sin referencias.
- raspberry/sincronizar.py: UUID y confirmaciones persistentes, manual/timer.
- backend/sincronizacion.js: igualdad numerica con tolerancia minima para evitar
  falsos conflictos por ultimos decimales; UUID con cambios reales devuelve 409.
- base-de-datos/001 y 002: ya ejecutadas. No repetir 001 ni suponer que reconstruyen
  toda la base. Falta exportar esquema inicial completo y funciones de recorridos.
- Pruebas individuales prueba_gps.py y prueba_mpu6050.py conservadas.

## Estado operativo al cerrar

Captura detenida por la usuaria, sincronizacion pausada deliberadamente durante
desarrollo. No se ejecutaron acciones sobre Raspberry/Supabase para crear este
respaldo. Confirmar estado real si hubo un reinicio posterior. `stop` no cambia
por si solo enable/disable; no asumir que el arranque coincide con el estado actual.
Backend nuevo probado en Windows; NO desplegado en Render. Frontend no se ha
validado contra todas las funciones nuevas. No publicar credenciales ni coordenadas.

## Validaciones locales del respaldo

15 pruebas Python pasaron (SQLite temporal, parsing, validacion temporal,
rotacion por cantidad/espacio, retencion, exportacion y reintentos simulados).
Seis pruebas Node pasaron. Estas pruebas no reemplazan las verificaciones de
hardware descritas y no prueban recuperacion ante cortes de energia.

## Recuperar el codigo sin borrar trabajo posterior

Preferir una carpeta nueva en Windows:

```powershell
git clone https://github.com/vkgtzs/dashguard.git dashguard-recuperacion
git -C dashguard-recuperacion switch --detach punto-recuperacion-2026-10-23
```

Inspeccionar y comparar archivos antes de copiarlos a Raspberry. Detener servicios
antes de reemplazar programas; respaldar SQLite con servicios detenidos. Las
migraciones ya aplicadas no deben ejecutarse como parte de una restauracion de
codigo. La etiqueta no revierte Supabase ni instala dependencias en Raspberry.

Para repetir el ensayo, mantener sincronizacion pausada, iniciar sensores,
calibrar inmovil y comprobar Guardado antes de iniciar camara. Detener sensores
solo DESPUES de Grabacion terminada. Revisar logs, temperatura, throttled y cuota.

## Pendientes y limites

No validados: horas de grabacion, arranque sin Internet/hora confiable, recuperacion
automatica de parciales tras corte electrico, garantia de continuidad frame a
frame y persistencia de PTS variables dentro del MP4 (sigue 15fps nominales).
No implementados: reconocimiento del conductor, eventos confiables, reportes,
gestor completo de recorridos offline, subida y visor de videos en backend.
Pendientes y evidencia protegida pueden crecer; cuota no limita SQLite, respaldos,
exportaciones ni carpetas de pruebas anteriores. Retencion real de siete dias
no se espero: regla verificada con prueba automatizada de datos sinteticos.
