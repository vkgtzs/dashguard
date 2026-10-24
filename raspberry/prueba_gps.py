import math
import time
import serial

PUERTO = "/dev/serial0"
CADUCIDAD = 10


def numero(texto):
    valor = float(texto)
    if not math.isfinite(valor):
        raise ValueError("Numero no finito")
    return valor


def coordenada(texto, hemisferio, latitud):
    valor = numero(texto)
    grados = int(valor / 100)
    minutos = valor - grados * 100
    limite = 90 if latitud else 180
    hemisferios = ("N", "S") if latitud else ("E", "W")

    if (
        valor < 0
        or not 0 <= minutos < 60
        or grados > limite
        or (grados == limite and minutos != 0)
        or hemisferio not in hemisferios
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


posicion = None
velocidad = None
ultimo_reporte = time.monotonic()
errores = 0

try:
    with serial.Serial(PUERTO, 9600, timeout=1) as puerto:
        puerto.reset_input_buffer()
        print("GPS iniciado. Ctrl+C para terminar.")

        while True:
            linea = puerto.read_until(b"\n", size=256)
            ahora = time.monotonic()

            if linea:
                try:
                    campos = campos_nmea(linea.decode("ascii").strip())
                    tipo = campos[0][-3:]

                    if tipo == "GGA":
                        posicion = None
                        calidad = int(campos[6])

                        if 1 <= calidad <= 5:
                            lat = coordenada(campos[2], campos[3], True)
                            lon = coordenada(campos[4], campos[5], False)
                            satelites = int(campos[7])
                            hdop = numero(campos[8])

                            if not 1 <= satelites <= 99 or hdop < 0:
                                raise ValueError("Calidad invalida")

                            posicion = (ahora, lat, lon, satelites, hdop)

                    elif tipo == "RMC":
                        velocidad = None

                        if campos[2] == "A":
                            # Validar tambien las coordenadas de RMC.
                            coordenada(campos[3], campos[4], True)
                            coordenada(campos[5], campos[6], False)

                            if campos[7]:
                                nudos = numero(campos[7])
                                if nudos < 0:
                                    raise ValueError("Velocidad invalida")
                                velocidad = (ahora, nudos * 1.852)

                except (ValueError, IndexError, UnicodeError):
                    errores += 1

            if ahora - ultimo_reporte >= 1:
                ultimo_reporte = ahora

                if posicion and ahora - posicion[0] <= CADUCIDAD:
                    _, lat, lon, satelites, hdop = posicion
                    texto = (
                        f"GPS VALIDO | Lat: {lat:.6f} | Lon: {lon:.6f} "
                        f"| Satelites: {satelites} | HDOP: {hdop:.2f}"
                    )

                    if velocidad and ahora - velocidad[0] <= CADUCIDAD:
                        texto += f" | Velocidad: {velocidad[1]:.2f} km/h"
                    else:
                        texto += " | Velocidad: no disponible"
                else:
                    texto = "SIN POSICION VALIDA RECIENTE"

                print(f"{texto} | Mensajes descartados: {errores}")

except KeyboardInterrupt:
    print("\nPrueba terminada.")
except serial.SerialException as error:
    print(f"Error del puerto serial: {error}")
