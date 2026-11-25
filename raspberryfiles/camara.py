"""Captura de foto y video corto con Picamera2.

La camara se abre solo durante cada captura y se libera al terminar,
para no ocupar memoria mientras no se usa. Mientras la camara esta en
uso se enciende el LED indicador, para que las personas en el vehiculo
sepan que se esta capturando.
"""
import threading
import time
from contextlib import contextmanager

candado = threading.Lock()  # una sola captura a la vez

RESOLUCION_FOTO = (1296, 972)
RESOLUCION_ANALISIS = (640, 480)
RESOLUCION_VIDEO = (1280, 720)
CUADROS_VIDEO = 15
BITRATE_VIDEO = 2_000_000
SEGUNDOS_VIDEO = 10
ESPERA_EXPOSICION_S = 1.5

# La camara va montada de cabeza en la carcasa: se gira 180 grados (volteo horizontal + vertical).
# Aplica a fotos, videos y a los cuadros del reconocimiento facial.
GIRAR_180 = True

PIN_LED = 26  # GPIO26, pin fisico 37
_led = None


def _indicador():
    """LED de captura; si no se puede usar, la captura sigue sin el."""
    global _led
    if _led is None:
        try:
            from gpiozero import LED
            _led = LED(PIN_LED)
        except Exception as error:
            print("LED indicador no disponible:", error, flush=True)
            _led = False
    return _led or None


@contextmanager
def _camara_en_uso():
    led = _indicador()
    if led:
        led.on()
    try:
        yield
    finally:
        if led:
            led.off()


def _orientacion():
    from libcamera import Transform

    return Transform(hflip=GIRAR_180, vflip=GIRAR_180)


def tomar_foto(ruta):
    from picamera2 import Picamera2

    with candado, _camara_en_uso():
        camara = Picamera2()
        try:
            camara.configure(camara.create_still_configuration(main={"size": RESOLUCION_FOTO},
                                                             transform=_orientacion()))
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

    with candado, _camara_en_uso():
        camara = Picamera2()
        try:
            camara.configure(camara.create_video_configuration(
                main={"size": RESOLUCION_VIDEO},
                controls={"FrameRate": CUADROS_VIDEO},
                transform=_orientacion()))
            camara.start_recording(H264Encoder(bitrate=BITRATE_VIDEO), FfmpegOutput(str(ruta)))
            time.sleep(segundos)
            camara.stop_recording()
        finally:
            camara.close()


@contextmanager
def cuadros(tamano=RESOLUCION_ANALISIS):
    """Abre la camara para analizar imagenes; entrega una funcion que devuelve el cuadro actual.

    El formato RGB888 de Picamera2 queda en orden BGR, el que usa OpenCV.
    """
    from picamera2 import Picamera2

    with candado, _camara_en_uso():
        camara = Picamera2()
        try:
            camara.configure(camara.create_preview_configuration(
                main={"size": tamano, "format": "RGB888"},
                transform=_orientacion()))
            camara.start()
            time.sleep(ESPERA_EXPOSICION_S)
            yield lambda: camara.capture_array("main")
            camara.stop()
        finally:
            camara.close()
