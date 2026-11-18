"""Verificacion facial del conductor con YuNet (deteccion) y SFace (reconocimiento).

Ambos modelos son ONNX y corren con el modulo DNN de OpenCV. Cada conductor
registrado se guarda como varios descriptores de 128 valores (uno por muestra).
Al comparar se usa la similitud coseno contra la mejor muestra de cada conductor.

Resultados posibles:
- autorizado: varios cuadros coinciden claramente con el mismo conductor.
- no_reconocido: varios cuadros con rostro util y ninguno se parece a un conductor.
- no_concluyente: sin rostro util, poca luz, rostro pequeno o comparacion dudosa.
"""
import json
import math
import time
from collections import Counter
from pathlib import Path

MODELOS = Path.home() / "dashguard" / "modelos"
ARCHIVO_YUNET = "face_detection_yunet_2023mar.onnx"
ARCHIVO_SFACE = "face_recognition_sface_2021dec.onnx"
CONDUCTORES = Path.home() / "dashguard" / "rostros" / "conductores.json"

CONFIANZA_DETECCION = 0.9
LADO_MINIMO_PX = 60
# SFace recomienda 0.363 de coseno para "misma persona". Debajo de 0.25 se
# considera otra persona; entre ambos valores la comparacion es dudosa.
# Pendiente calibrar con personas registradas y no registradas.
UMBRAL_AUTORIZADO = 0.363
UMBRAL_DESCONOCIDO = 0.25
CUADROS_AUTORIZADO = 3
CUADROS_DESCONOCIDO = 5
SEGUNDOS_MAXIMOS = 30
PAUSA_ENTRE_CUADROS_S = 0.4


class Rostros:
    """Carga los modelos; se crea solo cuando se va a usar para no ocupar memoria."""

    def __init__(self, carpeta=MODELOS):
        import cv2

        for archivo in (ARCHIVO_YUNET, ARCHIVO_SFACE):
            if not (carpeta / archivo).is_file():
                raise FileNotFoundError(f"Falta el modelo {carpeta / archivo}")
        self.detector = cv2.FaceDetectorYN.create(
            str(carpeta / ARCHIVO_YUNET), "", (320, 320), CONFIANZA_DETECCION, 0.3, 5000)
        self.reconocedor = cv2.FaceRecognizerSF.create(str(carpeta / ARCHIVO_SFACE), "")

    def cara_principal(self, imagen):
        """Cara mas grande de la imagen. Devuelve (cara, None) o (None, motivo)."""
        alto, ancho = imagen.shape[:2]
        self.detector.setInputSize((ancho, alto))
        _, caras = self.detector.detect(imagen)
        if caras is None or len(caras) == 0:
            return None, "sin_rostro"
        cara = max(caras, key=lambda c: c[2] * c[3])
        if min(cara[2], cara[3]) < LADO_MINIMO_PX:
            return None, "rostro_pequeno"
        return cara, None

    def descriptor(self, imagen, cara):
        alineada = self.reconocedor.alignCrop(imagen, cara)
        return [float(v) for v in self.reconocedor.feature(alineada).flatten()]


def similitud(a, b):
    producto = sum(x * y for x, y in zip(a, b))
    normas = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return producto / normas if normas else 0.0


def mejor_coincidencia(descriptor, conductores):
    """(conductor_id, similitud) del conductor mas parecido."""
    mejor = (None, -1.0)
    for conductor_id, datos in conductores.items():
        for muestra in datos["descriptores"]:
            valor = similitud(descriptor, muestra)
            if valor > mejor[1]:
                mejor = (conductor_id, valor)
    return mejor


def decidir(lecturas):
    """lecturas: lista de (conductor_id, similitud) de cuadros con rostro util."""
    coincidencias = Counter(c for c, s in lecturas if s >= UMBRAL_AUTORIZADO)
    if coincidencias:
        conductor, veces = coincidencias.most_common(1)[0]
        if veces >= CUADROS_AUTORIZADO:
            return "autorizado", conductor
    desconocidos = sum(1 for _, s in lecturas if s < UMBRAL_DESCONOCIDO)
    if desconocidos >= CUADROS_DESCONOCIDO and not coincidencias:
        return "no_reconocido", None
    return "no_concluyente", None


def verificar(rostros, conductores, obtener_cuadro, segundos=SEGUNDOS_MAXIMOS,
              pausa=PAUSA_ENTRE_CUADROS_S, reloj=time.monotonic, esperar=time.sleep):
    """Analiza cuadros hasta tener un resultado claro o agotar el tiempo."""
    inicio = reloj()
    lecturas, motivos, cuadros = [], Counter(), 0
    resultado, conductor = "no_concluyente", None
    while reloj() - inicio < segundos:
        imagen = obtener_cuadro()
        cuadros += 1
        cara, motivo = rostros.cara_principal(imagen)
        if cara is None:
            motivos[motivo] += 1
        else:
            lecturas.append(mejor_coincidencia(rostros.descriptor(imagen, cara), conductores))
            resultado, conductor = decidir(lecturas)
            if resultado != "no_concluyente":
                break
        esperar(pausa)
    return dict(
        resultado=resultado,
        conductor_id=conductor,
        cuadros=cuadros,
        cuadros_con_rostro=len(lecturas),
        mejor_similitud=round(max((s for _, s in lecturas), default=0.0), 3),
        motivos=dict(motivos),
        segundos=round(reloj() - inicio, 1),
    )


def cargar_conductores(ruta=CONDUCTORES):
    if not ruta.is_file():
        return {}
    return json.loads(ruta.read_text(encoding="utf-8"))


def guardar_conductores(conductores, ruta=CONDUCTORES):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(".tmp")
    temporal.write_text(json.dumps(conductores), encoding="utf-8")
    temporal.chmod(0o600)
    temporal.replace(ruta)


def verificar_en_camara(ruta_conductores=CONDUCTORES):
    """Verificacion completa con la camara del vehiculo."""
    conductores = cargar_conductores(ruta_conductores)
    if not conductores:
        return dict(resultado="no_concluyente", conductor_id=None, cuadros=0,
                    cuadros_con_rostro=0, mejor_similitud=0.0,
                    motivos={"sin_conductores_registrados": 1}, segundos=0.0)
    import camara

    rostros = Rostros()
    with camara.cuadros() as obtener_cuadro:
        return verificar(rostros, conductores, obtener_cuadro)
