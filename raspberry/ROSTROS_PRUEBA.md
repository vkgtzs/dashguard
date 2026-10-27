# Ensayo acotado de deteccion y video

`prueba_rostros.py` es un ensayo separado: no sustituye `video_espacio.py`, no toca
SQLite, no rota ni elimina archivos y no envia datos. No identifica al conductor.
Una Picamera2 produce main YUV420 1280x720 a 15 fps nominales, H264 hardware
aproximadamente 2 Mbps, y lores YUV420 320x180. Se copia luminancia y se libera la
solicitud antes de Haar/OpenCV. No se usa `VideoCapture` ni segunda camara.

Referencia primaria: [manual Picamera2](https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf).
La instalacion de referencia usa paquetes apt, no ruedas pip para ARM/Python 3.13:
`python3-picamera2`, `python3-opencv`, `opencv-data`. Comprobar versiones reales.

## Raspberry: procedimiento

Mantener sincronizacion pausada, verificar procesos y camara libre. Ejecutar
secuencialmente base y deteccion, nunca en paralelo. Cada salida debe ser nueva:

```bash
systemctl --user stop dashguard-sync.timer dashguard-sync.service
python3 prueba_rostros.py --modo base --duracion 60 --salida ~/dashguard/ensayos-rostros/base-01
python3 prueba_rostros.py --modo deteccion --duracion 60 --hz 2 --salida ~/dashguard/ensayos-rostros/deteccion-01
```

Durante deteccion: colocar un rostro frontal visible y despues retirar el rostro;
anotar condiciones reales. No hay medida de exactitud sin etiquetas independientes.
No usar oscuridad o ausencia para inferir persona no autorizada.

Limites: 10–180 s por ejecucion, 0.2–5 Hz solicitados, alarma de seguridad,
256 MiB libres requeridos, permisos privados, carpeta nueva obligatoria.
No incluye cuota continua: un ensayo de 180 s puede ocupar aproximadamente 90 MB
sumando H264 y MP4. Conservar evidencia; no repetir indefinidamente sin revisar disco.

Salida privada: H264 original, PTS del codificador, MP4 por copia, `ffprobe.json`
y `metricas.json`. No subir a Git ni servicios publicos. El JSON guarda tiempos,
rectangulos y luminancia, sin fotos separadas, coordenadas GPS ni plantillas.
El video contiene imagen del conductor y debe permanecer privado.

Comparar duracion, frames decodificados y frames de metadata, PTS, FPS real,
huecos >100 ms, latencia media/p95, frecuencia efectiva, CPU proceso (100%=un nucleo),
carga del sistema, ticks CPU, RAM residente/disponible, temperatura y throttled.
Los callbacks cuentan solicitudes observadas, no garantizan por si solos entrega
al codificador. MP4 conserva 15 fps nominales: usar PTS originales para la cadencia.
Carga media no equivale a porcentaje de CPU. La base conserva lores para aislar
el costo adicional de deteccion. No equivale aun a integrar deteccion con cuota,
segmentacion y sensores de produccion.
