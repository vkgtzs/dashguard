# Grabacion con cuota: validar primero tres minutos

Requiere registrador con boottime_ns, retencion.py, ffmpeg/ffprobe y rpicam-vid.
No ejecuta ni habilita sincronizacion. No instala servicio al arranque.

```bash
python3 ~/video_espacio.py --duracion 180 --segmento 10 --limite-mib 30
```

Usa una instancia rpicam y procesa segmentos cerrados mientras sigue grabando.
Metadata stdout y PTS pipe se drenan mediante dos hilos, para que ffprobe/ffmpeg
no bloqueen directamente esos pipes. La version instalada debe admitir metadata
en stdout y save-pts hacia /proc/self/fd; pendiente verificar en Raspberry.
Los lectores solo conservan SensorTimestamp; otros campos de camara se descartan.
Valida secuencia PTS relativa con SensorTimestamp y conteo por segmento.
El error de alineacion detiene grabacion, conservando brutos y tiempos pendientes.

Carpeta exclusiva ~/dashguard/videos/loop_espacio. Tabla videos_espacio.
Cuenta TODOS los archivos bajo esa carpeta, incluidos activos, parciales y JSON.
Solo elimina MP4/JSON registrados y no protegidos, del mas antiguo al reciente.
Conserva referencias de otras pruebas. Para proteger un clip, detener grabacion
y UPDATE videos_espacio SET protegido=1 WHERE id='UUID'; no hay interfaz de eventos.

La cuota es operativa/blanda: comprueba periodicamente y reserva espacio de trabajo
calculado para 2 Mbps; el archivo activo y conversion pueden superar temporalmente
la estimacion. Si protegidos/parciales impiden cumplirla se detiene, no los borra.
Requiere 256 MiB libres en el sistema durante grabacion. No limita SQLite ni
otras carpetas de prueba; pendientes y videos protegidos requieren administracion.
No garantiza continuidad si la CPU/SD no soporta lectura/conversion simultanea.
Si se acumulan mas de 10000 timestamps o falta progreso se detiene.

Retencion: limpiar confirmadas con captura y confirmacion >7 dias sin vinculos
a videos retenidos; se ejecuta aproximadamente cada minuto y al terminar.
No borra Supabase, pendientes ni respaldos. SQLite reutiliza paginas, no VACUUM.

Limites de tiempo: IMU a 1 Hz con marca del host antes de I2C. GPS ultimo fix
reciente (hasta diez segundos), no adquisicion simultanea. JSON conserva tiempos
de frames originales; MP4 sigue 15fps nominales, no cadencia variable garantizada.
Ultimo segmento termina en ultimo timestamp+1ns sin extrapolar exposicion.

--duracion 0 graba hasta Ctrl+C; no usar horas antes de validar recursos.
Ctrl+C detiene la camara, pero el ultimo segmento puede quedar sin procesar:
se conservan brutos y tiempos pendientes para recuperacion manual; sin recuperacion
automatica ante cortes electricos ni garantia de cerrar MP4 ante falta de energia.
No se borran esos parciales automaticamente en siguiente arranque.
Usa bloqueo para evitar dos instancias de ESTE programa; no bloquea otras apps
de camara. Una cuota baja puede detenerse al acumular parciales de ensayos fallidos.

Archivos de prueba anteriores quedan fuera de cuota. No llamar cuota global del
dispositivo ni retencion total de datos. No se implementa aun subida de videos.

Pruebas PC: parser incremental, validacion de tiempos, cuota con protegidos,
referencias y parciales. Pendiente prueba real de tres minutos, luego 15-30 minutos
con temperatura/carga y verificacion de reproduccion antes de varias horas.
