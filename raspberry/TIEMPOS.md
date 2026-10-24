# Diagnostico previo a cambiar la vinculacion

prueba_tiempos.py graba 15 segundos con metadata JSON y save-pts. No lee ni
modifica SQLite ni inicia sincronizacion. Requiere rpicam-vid y Python estandar.
No ejecutar junto con otro proceso de camara. Los archivos quedan en una
carpeta UUID bajo ~/dashguard/videos/tiempos; no tienen limpieza automatica.

SensorTimestamp usa CLOCK_BOOTTIME en nanosegundos. El registrador actual usa
time.monotonic. No asumir que son el mismo reloj: el diagnostico mide su
diferencia antes y despues, importante si hubo suspension. Para la integracion
definitiva usar mismo reloj y boot_id. No modificar muestras historicas.

El script reporta intervalos de SensorTimestamp y conteos metadata/PTS. Un
intervalo grande indica posible irregularidad, no prueba causal de perdidas.
Coincidir conteos no prueba por si solo correspondencia por fotograma.
La prueba no altera video_continuo.py: hasta validar hardware sigue usando
ventanas aproximadas. Falta repartir fotogramas por segmento, validar alineacion
entre metadata y stream, y conservar PTS reales en contenedor reproducible.

Fuentes oficiales:
- https://github.com/raspberrypi/libcamera/blob/main/src/libcamera/control_ids_core.yaml
- https://github.com/raspberrypi/rpicam-apps/blob/main/output/output.cpp

Pruebas de analisis con datos sinteticos: test_tiempos.py. Pendiente ejecucion
en la Raspberry con la version instalada de rpicam.
