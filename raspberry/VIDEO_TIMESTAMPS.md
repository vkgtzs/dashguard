# Asociacion con tiempos del sensor: prueba acotada

No reemplaza video_continuo.py. Instalar registrador actualizado (parado primero),
retencion.py y video_timestamps.py. Guardar respaldo de registrador y SQLite con
captura y sincronizacion detenidas. Iniciar captura, calibrar inmovil y ejecutar
video_timestamps.py. No se reactiva sincronizacion ni se toca Supabase.

Captura 90 s en una instancia rpicam. Procesa al FINALIZAR para acceder a metadata
JSON completa. Reserva minima inicial 512 MiB; vigila 256 MiB durante captura.
No es loop indefinido: conserva temporalmente todos los brutos del ensayo antes
de rotar a seis MP4/JSON no protegidos. Los protegidos quedan fuera del limite.
Carpeta timestamps_prueba, tabla videos_timestamps; no rota otras pruebas.

Cuenta frames decodificados de cada H264 con ffprobe, verifica suma contra PTS
y metadata, verifica orden y secuencia de tiempos relativos (tolerancia 0.1 ms).
Falla conservando brutos si no alinea. La particion de frames es por orden del
stream: validar en hardware que metadata corresponde al mismo orden codificado.
Esto es mas fuerte que conteos solos pero aun requiere prueba de reproduccion
y continuidad real. No afirmar precision fisica exacta de IMU/GPS.

SensorTimestamp usa CLOCK_BOOTTIME. El registrador agrega boottime_ns del host
antes de leer I2C y boot_id. No se convierte ni modifica historia anterior.
GPS sigue siendo ultimo fix valido hasta diez segundos: NO es lectura simultanea
al fotograma ni se interpola trayectoria. IMU sigue a 1 Hz.

Ventanas [primer frame, primer frame siguiente); ultimo segmento termina en
ultimo frame+1ns, sin inventar duracion posterior. No se aplica margen heuristico.
JSON guarda timestamps y PTS originales de cada frame, muestras y limites.
MP4 sigue empaquetado a 15fps nominales: aun no preserva cadencia variable dentro
del contenedor. No usar su posicion de reproduccion para timing exacto si hubo
frames perdidos. Originales metadata/PTS se conservan en sesion_UUID; no se limpian
automaticamente y pueden contener datos de segmentos ya rotados.

Retencion de muestras igual: ambas fechas (captura/confirmacion) >7 dias, no
pendientes ni referencias de videos retenidos. Al finalizar detener captura
manualmente. No se instala servicio automatico ni se publica esta prueba aun.

Pruebas PC: particion, ausencia de solapamientos, ultimo frame, rechazo de
conteos/desalineacion. Falta validacion con archivos reales del ensayo Pi.
