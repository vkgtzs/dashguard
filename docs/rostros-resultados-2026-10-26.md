# Rostros y grabacion: resultados reales, 26 de octubre de 2026

Raspberry Pi Zero 2 W, armv7l, Camera ov5647, Picamera2 0.3.37,
libcamera v0.7.2+rpt20260817, Python del sistema 3.13, OpenCV 4.10.0.
Una sola Picamera2: main YUV420 1280x720, H264 2 Mbps/15 fps nominales;
lores YUV420 320x180. Haar frontal, minNeighbors=5, minSize=30x30,
scaleFactor=1.1, un hilo OpenCV. Se libera request antes del analisis.

## Estado conservado

Acceso SSH autenticado real. Captura de sensores detenida; sincronizador y timer
inactivos; timer deshabilitado. No se enviaron muestras ni se toco Supabase.
SHA256 de dashguard_local.py, imu_segura.py, sincronizar.py y video_espacio.py
coinciden entre Windows y Raspberry. Cambio IMU/GPS respaldado en `1a838c2`.
No se modificaron estos programas en Raspberry ni se borraron datos.

APT fallo por conexiones al repositorio y baja velocidad. Windows descargo 46
paquetes con SHA256 comprobado contra catalogo APT de la Raspberry; junto a 15
ya en cache se extrajeron en carpeta de usuario. OpenCV cargo sin sudo, mediante
PYTHONPATH/LD_LIBRARY_PATH limitados al proceso. No confundir con instalacion
global de python3-opencv en dpkg. Coral no conectado ni usado por el ensayo.

## Comparacion secuencial de 60 segundos

| Medida | Base, sin analisis | Con detector |
|---|---:|---:|
| Ventana real de captura (s) | 60.003 | 60.004 |
| Cadencia por PTS/SensorTimestamp (fps) | 15.003 | 15.002 |
| Fotogramas decodificados / PTS / metadata | 891 / 891 / 891 | 891 / 891 / 891 |
| Intervalos >100 ms | 0 | 0 |
| Analisis y frecuencia efectiva | 0 | 120; 2.000 Hz |
| Analisis medio / p95 / maximo (ms) | — | 98.26 / 128.70 / 156.39 |
| Captura+copia+analisis medio / p95 / maximo (ms) | — | 109.65 / 134.95 / 788.30 |
| CPU proceso (100%=un nucleo) | 23.92% | 38.24% |
| CPU global media (todos los nucleos) | 6.11% | 9.54% |
| Carga maxima de 1 minuto | 1.191 | 0.824 |
| RSS maxima (MiB) | 39.71 | 112.99 |
| Memoria disponible minima (MiB) | 271.16 | 253.02 |
| Temperatura maxima observada | 48.31 C | 48.31 C |
| throttled observado | 0x0 | 0x0 |
| Analisis con rostro | no evaluado | 0 de 120 |

La carga de un minuto conserva historia previa y no mide solo este proceso.
RSS incluye paginas compartidas; no es incremento neto de RAM global.
La ventana de control no es la duracion exacta del flujo codificado: 891 frames
a 15 fps nominales producen unos 59.4 s de MP4; medir cadencia en PTS originales.
No hay prueba independiente de ausencia absoluta de perdidas antes de callbacks.
No se observa regresion de cadencia ni discrepancia de conteos en estas ventanas.

Un ensayo previo de 15 s de la nueva ruta de camara produjo 216 frames, 14.999 fps
y conteos coincidentes. Coincidio con instalacion y no se uso para comparar CPU.
La verificacion ffprobe de 60 s excedio el primer limite de 30 s; se amplio a
120 s y se verifico el bruto existente sin repetir ni borrar la captura base.
El tiempo de decodificar despues no debe confundirse con el costo de grabar.

## Calidad y limites

La revision visual de un fotograma del primer ensayo con detector mostro rostro
girado, demasiado cerca y recortado por bordes. Cero detecciones no se interpreta
como persona no autorizada. Se conserva ese resultado y se solicita encuadre frontal
completo para un segundo ensayo, sin cambiar modelo ni umbrales.

El segundo ensayo frontal real duro 30.014 s: **56 de 60 analisis con rostro**,
1.999 Hz, analisis medio 148.58 ms, p95 179.85 ms y maximo 194.62 ms.
Captura+copia+analisis: media 166.01 ms, p95 188.80 ms, maximo 829.40 ms
(incluye espera inicial de imagen). Video a 15.002 fps por PTS, 441 frames
decodificados / 441 PTS / 441 metadata, cero huecos >100 ms.
CPU proceso 48.37% de un nucleo; CPU global media 12.35%, p95 13.65%.
Carga maxima de un minuto 0.384; RSS maxima 112.94 MiB; memoria disponible minima
256.55 MiB; temperatura maxima 48.31 C; throttled=0x0.
Esto demuestra deteccion positiva con grabacion en una escena controlada. La
fraccion 56/60 no es exactitud: no se etiquetaron todos los frames ni se evaluaron
falsos positivos/negativos con un conjunto independiente. No se seleccionaron
umbrales despues para borrar el resultado negativo anterior.

Estas ventanas no incluyen sensores activos, rotacion por cuota ni eventos en
produccion. No demuestran horas de operacion en vehiculo, exactitud de detector,
identidad ni resistencia a fotografias. La simulacion de fallo IMU sigue siendo
simulacion; no se hizo desconexion fisica nueva.

## Decision siguiente

El rendimiento permite continuar con Raspberry sola: no se justifica introducir
Coral con estas mediciones. La deteccion positiva en encuadre frontal ya se cerro.
Evaluar LBPH disponible en esta instalacion como primer candidato ligero
para una demostracion controlada, midiendo tambien su latencia y rechazo de
personas no enroladas. Su disponibilidad no prueba su precision. Si no separa
identidades/condiciones de forma suficiente, comparar un modelo de embeddings
CPU compatible antes de introducir acelerador.

El proximo entregable integrado debe unir rostro util, enrolamiento/comparacion,
estado autorizado/desconocido/incierto y evento local con clip conservado,
manteniendo una sola sesion y recuperando catalogo/cuota y sensores funcionales.
No lanzar este ensayo en paralelo a video_espacio.py. Mantener su version estable
hasta validar la migracion de captura a Picamera2. Priorizar esto sobre interfaz.

Evidencia privada en Raspberry: `~/dashguard/ensayos-rostros/` y copia en Windows
`github-dashguard/ensayos-rostros/` (ignorada por Git). Videos, imagenes y JSON
detallados permanecen fuera del repositorio. Este documento contiene solo agregados.
