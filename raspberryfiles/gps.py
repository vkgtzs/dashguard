"""Lectura del GPS NEO-6M (sentencias NMEA GGA y RMC)."""
import math
import threading
import time

CADUCIDAD_S = 10
RADIO_TIERRA_M = 6371008.8


def _numero(texto):
    valor = float(texto)
    if not math.isfinite(valor):
        raise ValueError("Numero no finito")
    return valor


def coordenada(texto, hemisferio, es_latitud):
    # ddmm.mmmm -> grados decimales
    valor = _numero(texto)
    grados = int(valor / 100)
    minutos = valor - grados * 100
    limite = 90 if es_latitud else 180
    permitidos = ("N", "S") if es_latitud else ("E", "W")
    if (
        valor < 0 or not 0 <= minutos < 60
        or grados > limite
        or (grados == limite and minutos != 0)
        or hemisferio not in permitidos
    ):
        raise ValueError("Coordenada invalida")
    resultado = grados + minutos / 60
    return -resultado if hemisferio in ("S", "W") else resultado


def campos_nmea(linea):
    if not linea.startswith("$") or "*" not in linea:
        raise ValueError("Mensaje incompleto")
    cuerpo, checksum = linea[1:].split("*", 1)
    if len(checksum) != 2:
        raise ValueError("Checksum incompleto")
    calculado = 0
    for caracter in cuerpo:
        calculado ^= ord(caracter)
    if calculado != int(checksum, 16):
        raise ValueError("Checksum incorrecto")
    return cuerpo.split(",")


def distancia_m(lat1, lon1, lat2, lon2):
    # Haversine
    f1, f2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((f2 - f1) / 2) ** 2
         + math.cos(f1) * math.cos(f2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * RADIO_TIERRA_M * math.asin(math.sqrt(a))


class EstadoGPS:

    def __init__(self, reloj=time.monotonic):
        self._reloj = reloj
        self._candado = threading.Lock()
        self._posicion = None   # (instante, latitud, longitud, satelites, hdop)
        self._velocidad = None  # (instante, km/h)

    def procesar(self, linea):
        try:
            campos = campos_nmea(linea.strip())
            tipo = campos[0][-3:]
            ahora = self._reloj()
            if tipo == "GGA":
                with self._candado:
                    self._posicion = None
                if 1 <= int(campos[6]) <= 5:
                    latitud = coordenada(campos[2], campos[3], True)
                    longitud = coordenada(campos[4], campos[5], False)
                    satelites = int(campos[7])
                    hdop = _numero(campos[8])
                    if not 1 <= satelites <= 99 or hdop < 0:
                        raise ValueError("Calidad invalida")
                    with self._candado:
                        self._posicion = (ahora, latitud, longitud, satelites, hdop)
            elif tipo == "RMC":
                with self._candado:
                    self._velocidad = None
                if campos[2] == "A" and campos[7]:
                    nudos = _numero(campos[7])
                    if nudos < 0:
                        raise ValueError("Velocidad invalida")
                    with self._candado:
                        self._velocidad = (ahora, nudos * 1.852)
        except (ValueError, IndexError):
            pass

    def invalidar(self):
        with self._candado:
            self._posicion = None
            self._velocidad = None

    def lectura(self):
        ahora = self._reloj()
        resultado = dict(valido=False, latitud=None, longitud=None,
                         satelites=None, hdop=None, velocidad_kmh=None)
        with self._candado:
            posicion, velocidad = self._posicion, self._velocidad
        if posicion and ahora - posicion[0] <= CADUCIDAD_S:
            _, latitud, longitud, satelites, hdop = posicion
            resultado.update(valido=True, latitud=latitud, longitud=longitud,
                             satelites=satelites, hdop=hdop)
            if velocidad and ahora - velocidad[0] <= CADUCIDAD_S:
                resultado["velocidad_kmh"] = velocidad[1]
        return resultado


def leer_puerto(estado, parar, puerto="/dev/serial0", baudios=9600):
    import serial

    try:
        with serial.Serial(puerto, baudios, timeout=1) as conexion:
            conexion.reset_input_buffer()
            while not parar.is_set():
                linea = conexion.read_until(b"\n", size=256)
                if linea:
                    try:
                        estado.procesar(linea.decode("ascii"))
                    except UnicodeError:
                        continue
    except (serial.SerialException, OSError) as error:
        estado.invalidar()
        print(f"GPS detenido: {error}", flush=True)
