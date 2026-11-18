"""Captura de foto y video corto con Picamera2.

La camara se abre solo durante cada captura y se libera al terminar,
para no ocupar memoria mientras no se usa.
"""
import threading
import time

candado = threading.Lock()  # una sola captura a la vez

RESOLUCION_FOTO = (1296, 972)
RESOLUCION_VIDEO = (1280, 720)
CUADROS_VIDEO = 15
BITRATE_VIDEO = 2_000_000
SEGUNDOS_VIDEO = 10
ESPERA_EXPOSICION_S = 1.5


def tomar_foto(ruta):
    from picamera2 import Picamera2

    with candado:
        camara = Picamera2()
        try:
            camara.configure(camara.create_still_configuration(main={"size": RESOLUCION_FOTO}))
            camara.options["quality"] = 85
            camara.start()
            time.sleep(ESPERA_EXPOSICION_S)
            camara.capture_file(str(ruta))
            camara.stop()
        finally:
            camara.close()


def grabar_video(ruta, segundos=SEGUNDOS_VIDEO):
    from picamera2 import Picamera2
    from picamera2.encoders import H264Encoder
    from picamera2.outputs import FfmpegOutput

    with candado:
        camara = Picamera2()
        try:
            camara.configure(camara.create_video_configuration(
                main={"size": RESOLUCION_VIDEO},
                controls={"FrameRate": CUADROS_VIDEO}))
            camara.start_recording(H264Encoder(bitrate=BITRATE_VIDEO), FfmpegOutput(str(ruta)))
            time.sleep(segundos)
            camara.stop_recording()
        finally:
            camara.close()
