# DashGuard

Sistema embebido de seguridad del conductor con Raspberry Pi Zero 2 W.

## Estado verificado al 23 de octubre de 2026

- MPU6050 I2C y GPS NEO-6M UART funcionando en Raspberry.
- Captura en SQLite y UUID por muestra; reintentos sin duplicar en Supabase.
- Backend actualizado probado en Windows, no desplegado aun en Render.
- Servicios de captura y sincronizacion probados despues de reiniciar.
- Video 720p/15 fps segmentado, MP4 reproducibles y JSON con IMU/GPS.
- Prueba de 90 segundos con una captura de camara y rotacion a seis clips.
- Asociacion temporal de videos aproximada; pendiente usar timestamps reales.
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

El codigo de reconocimiento del conductor, gestion offline completa de recorridos,
grabacion indefinida y reportes finales aun no esta implementado.

## Limites de este respaldo

Respalda archivos del PC. No se pudo autenticar SSH automaticamente para verificar
que coincidan exactamente con la Raspberry. Recuperar desde ella prueba_gps.py,
prueba_mpu6050.py y las versiones actuales antes de afirmar paridad. gps.py local
es un archivo incompleto y mpu6050.py usa otro nombre; no reemplazan esas pruebas.
No se publican bases, videos, exportaciones personales ni claves.

Consultar README de backend y raspberry para instalacion y operacion.
