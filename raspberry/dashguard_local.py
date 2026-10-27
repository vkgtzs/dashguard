import json
import argparse
import math
import queue
import sqlite3
import threading
import time
from pathlib import Path

import serial
from smbus import SMBus
from imu_segura import IMUSegura

DIRECCION = 0x68
CADUCIDAD_GPS = 10
CARPETA = Path.home() / "dashguard" / "datos"
CARPETA.mkdir(parents=True, exist_ok=True)
BOOT_ID = Path('/proc/sys/kernel/random/boot_id').read_text().strip()

parar = threading.Event()
gps_lock = threading.Lock()
gps_estado = {"posicion": None, "velocidad": None}
avisos = queue.SimpleQueue()


def entero16(datos, inicio):
    valor = (datos[inicio] << 8) | datos[inicio + 1]
    return valor - 65536 if valor >= 32768 else valor


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
    permitidos = ("N", "S") if latitud else ("E", "W")

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


def leer_gps():
    try:
        with serial.Serial("/dev/serial0", 9600, timeout=1) as puerto:
            puerto.reset_input_buffer()
            while not parar.is_set():
                linea = puerto.read_until(b"\n", size=256)
                if not linea:
                    continue

                try:
                    campos = campos_nmea(linea.decode("ascii").strip())
                    tipo = campos[0][-3:]
                    ahora = time.monotonic()

                    if tipo == "GGA":
                        with gps_lock:
                            gps_estado["posicion"] = None

                        calidad = int(campos[6])
                        if 1 <= calidad <= 5:
                            lat = coordenada(campos[2], campos[3], True)
                            lon = coordenada(campos[4], campos[5], False)
                            satelites = int(campos[7])
                            hdop = numero(campos[8])
                            if not 1 <= satelites <= 99 or hdop < 0:
                                raise ValueError("Calidad invalida")
                            with gps_lock:
                                gps_estado["posicion"] = (
                                    ahora, lat, lon, satelites, hdop
                                )

                    elif tipo == "RMC":
                        with gps_lock:
                            gps_estado["velocidad"] = None

                        if campos[2] == "A":
                            coordenada(campos[3], campos[4], True)
                            coordenada(campos[5], campos[6], False)
                            if campos[7]:
                                nudos = numero(campos[7])
                                if nudos < 0:
                                    raise ValueError("Velocidad invalida")
                                with gps_lock:
                                    gps_estado["velocidad"] = (
                                        ahora, nudos * 1.852
                                    )
                except (ValueError, IndexError, UnicodeError):
                    continue

    except (serial.SerialException, OSError) as error:
        with gps_lock:
            gps_estado["posicion"] = None
            gps_estado["velocidad"] = None
        avisos.put(f"GPS detenido: {error}. La IMU seguira registrando.")


def obtener_gps():
    ahora = time.monotonic()
    resultado = {
        "gps_valido": False,
        "latitud": None,
        "longitud": None,
        "satelites": None,
        "hdop": None,
        "velocidad_kmh": None,
    }

    with gps_lock:
        posicion = gps_estado["posicion"]
        velocidad = gps_estado["velocidad"]

    if posicion and ahora - posicion[0] <= CADUCIDAD_GPS:
        _, lat, lon, satelites, hdop = posicion
        resultado.update(
            gps_valido=True,
            latitud=lat,
            longitud=lon,
            satelites=satelites,
            hdop=hdop,
        )
        if velocidad and ahora - velocidad[0] <= CADUCIDAD_GPS:
            resultado["velocidad_kmh"] = velocidad[1]

    return resultado


bus = None
db = None
hilo = None

try:
    argumentos = argparse.ArgumentParser()
    argumentos.add_argument('--simular-fallo-imu', action='store_true',
                            help='No accede a IMU; guarda GPS y fallo simulado localmente')
    opciones = argumentos.parse_args()
    db = sqlite3.connect(CARPETA / "dashguard.sqlite3")
    db.execute("""
        CREATE TABLE IF NOT EXISTS muestras (
            id INTEGER PRIMARY KEY,
            fecha_hora_pc TEXT NOT NULL,
            monotonic_s REAL NOT NULL,
            datos_json TEXT NOT NULL
        )
    """)
    db.commit()
    if 'boot_id' not in {c[1] for c in db.execute('PRAGMA table_info(muestras)')}:
        db.execute('ALTER TABLE muestras ADD COLUMN boot_id TEXT')
        db.commit()
    if 'boottime_ns' not in {c[1] for c in db.execute('PRAGMA table_info(muestras)')}:
        db.execute('ALTER TABLE muestras ADD COLUMN boottime_ns INTEGER')
        db.commit()

    hilo = threading.Thread(target=leer_gps, daemon=True)
    hilo.start()
    imu = IMUSegura(None)
    if opciones.simular_fallo_imu:
        imu.fallar('fallo_simulado')
    else:
        try:
            bus = SMBus(1)
            imu = IMUSegura(bus)
            print('Calibrando giroscopio: manten el sensor quieto.')
            imu.inicializar()
        except OSError as error:
            imu.fallar(str(error))
    print('Estado inicial IMU:', imu.error or 'calibrada', '| Offsets:', imu.offsets)
    print("Guardando una muestra por segundo. Ctrl+C para terminar.")
    print("Base de datos:", CARPETA / "dashguard.sqlite3")

    while True:
        inicio = time.monotonic()
        while not avisos.empty():
            print(avisos.get())

        # Marca del host inmediatamente antes de leer I2C; no timestamp interno IMU.
        captura_ns = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        muestra = {
            **imu.leer(),
            **obtener_gps(),
            'prueba_fallo_imu': opciones.simular_fallo_imu,
        }
        # Esta fecha viene del reloj del sistema, no del GPS.
        fecha = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        cursor = db.execute(
            """INSERT INTO muestras
               (fecha_hora_pc, monotonic_s, datos_json, boot_id, boottime_ns)
               VALUES (?, ?, ?, ?, ?)""",
            (fecha, inicio, json.dumps(muestra, allow_nan=False), BOOT_ID, captura_ns),
        )
        db.commit()

        estado = "GPS valido" if muestra["gps_valido"] else "Sin GPS valido"
        estado_imu = (f"A: {muestra['magnitud_ms2']:.2f} m/s2" if muestra['imu_valida']
                      else f"IMU NO VALIDA: {muestra['imu_error']} (reiniciar captura tras revisar sensor)")
        print(
            f"Guardado #{cursor.lastrowid} | {estado} "
            f"| {estado_imu}"
        )
        parar.wait(max(0, 1 - (time.monotonic() - inicio)))

except KeyboardInterrupt:
    print("\nRegistro detenido.")
except (OSError, sqlite3.Error, RuntimeError) as error:
    print(f"ERROR: {error}")
finally:
    parar.set()
    if hilo:
        hilo.join(timeout=2)
    if db:
        db.close()
    if bus:
        bus.close()
