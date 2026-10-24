# DashGuard

Sistema embebido de seguridad del conductor con Raspberry Pi Zero 2 W.

## Estado verificado al 23 de octubre de 2026

- MPU6050 I2C y GPS NEO-6M UART funcionando en Raspberry.
- Captura en SQLite y UUID por muestra; reintentos sin duplicar en Supabase.
- Backend actualizado probado en Windows, no desplegado aun en Render.
- Servicios de captura y sincronizacion probados despues de reiniciar.
- Video 720p/15 fps segmentado, MP4 reproducibles y JSON con IMU/GPS.
- Prueba de 15 minutos con una captura de camara, GPS e IMU y rotacion por espacio.
- Asociacion por SensorTimestamp y CLOCK_BOOTTIME del host; no implica lectura
  simultanea ni precision fisica por fotograma de IMU/GPS.
- Exportacion de cinco segmentos a un MP4 reproducible: 786 frames y 52.40 s,
  con JSON unico de telemetria. Los segmentos rotados no se recuperan.
- Limpieza de muestras confirmadas con mas de siete dias, salvo vinculadas a
  videos retenidos. Pendientes y evidencia protegida no se descartan.

Sincronizacion y captura se mantienen pausadas durante desarrollo salvo pruebas
explicitas. No reactivar envios automaticamente al seguir estas instrucciones.

## Carpetas

- backend: API y pruebas; configurar .env desde .env.example, nunca publicarlo.
- raspberry: captura, sincronizador, pruebas y servicios systemd de usuario.
- base-de-datos: migraciones 001 y 002 YA aplicadas. No son esquema completo.
- frontend: copia local aportada; apunta a Render, integracion nueva pendiente.
- El prototipo ESP32 aun no esta incluido sin credenciales; su carpeta vacia
  fue eliminada previamente en GitHub y se respeto ese cambio.

Reconocimiento del conductor, gestion offline completa de recorridos y reportes
finales aun no implementados. Modo de duracion ilimitada disponible pero NO
validado durante horas; corte electrico y recuperacion automatica pendientes.

## Limites de este respaldo

Respalda archivos del PC. No se pudo autenticar SSH automaticamente para verificar
que coincidan exactamente con la Raspberry. Ya estan presentes prueba_gps.py y
prueba_mpu6050.py en el respaldo local; se conserva la reorganizacion aportada.
No se afirma igualdad byte a byte con los archivos actualmente instalados.
No se publican bases, videos, exportaciones personales ni claves.

Consultar README de backend y raspberry para instalacion y operacion.

Punto de recuperacion: [prueba integrada de 15 minutos](docs/punto-recuperacion-2026-10-23.md).
