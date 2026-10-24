# Prueba continua de 90 segundos

Ejecutar video_continuo.py junto al servicio de captura de sensores. Requiere
retencion.py y el registrador actualizado con boot_id. No activa sincronizacion.
Una sola instancia rpicam-vid segmenta cada diez segundos solicitados; la
conversion por copia de codec se realiza al aparecer el siguiente segmento.
La camara no se reinicia entre clips. No se ha comprobado aun perdida de frames
o continuidad temporal real en hardware bajo esta carga.

Conserva seis MP4/JSON no protegidos en ~/dashguard/videos/continuo_prueba.
Usa tabla videos_continuos para no rotar los archivos de loop_prueba.
video_muestras es compartida con la limpieza: conserva muestras referenciadas.
Proteccion manual: detener video y UPDATE videos_continuos SET protegido=1
WHERE id='UUID'. Los protegidos no cuentan en los seis y pueden ocupar mas espacio.
Pendientes no se borran. Solo confirmados y capturados hace mas de siete dias
pueden borrarse si ningun video retenido los referencia.

La vinculacion temporal es APROXIMADA: detecta aparicion de archivos usando
time.monotonic y boot_id, con margen heuristico de un segundo. La deteccion
puede retrasarse por conversion/SQLite/escritura, sin error maximo garantizado.
Puede incluir muestras de segmentos adyacentes. No equivale a asociacion por
fotograma ni usa timestamps del sensor de camara. FPS nominal 15 al empaquetar:
si hay frames perdidos, la duracion MP4 puede diferir del tiempo real.
No utilizar esta aproximacion para inferir el instante exacto de un incidente.
Siguiente mejora: timestamps reales de fotogramas y verificacion de continuidad.

Aborta si baja de 512 MiB libres. Interrupciones/errores conservan archivos
brutos o parciales; no hay recuperacion automatica. Directorios captura_UUID
pueden quedar vacios. No es servicio de grabacion indefinida; se detiene a 90 s.
El registrador de sensores NO se detiene automaticamente al finalizar video.

Verificacion PC: sintaxis y rotacion con archivos simulados, incluida proteccion
y conservacion de referencias de otros videos. Pendiente validar en Raspberry.
