"""DashGuard v2 en la Raspberry.

- Abre y cierra recorridos segun el movimiento (IMU, o GPS si la IMU falla).
- Registra un punto GPS cada pocos segundos y la distancia recorrida.
- Genera alerta de exceso de velocidad con el limite configurado en la app.
- Verifica el rostro del conductor al iniciar cada recorrido.
- Atiende los comandos de foto o video que pide el supervisor.
- Todo pasa por la cola local (almacen) y se sincroniza con el backend.

Uso:
    python3 dashguard.py                  # funcionamiento normal
    python3 dashguard.py --probar-camara  # toma una foto y un video y termina
"""
import argparse
import queue
import signal
import threading
import time
import uuid
from pathlib import Path

import almacen
import camara
import gps
import rostros
import sincronizar
from imu import IMU, DetectorMovimiento
from velocidad import DetectorExceso

BASE = Path.home() / "dashguard"
CONFIG = BASE / "config" / "dispositivo.json"
DB = BASE / "datos" / "dashguard-v2.sqlite3"
EVIDENCIAS = BASE / "evidencias"

SEGUNDOS_CICLO = 0.5
SEGUNDOS_PUNTO = 5
SEGUNDOS_RED = 10
LIMITE_PREDETERMINADO_KMH = 80
VELOCIDAD_MINIMA_DISTANCIA_KMH = 3   # evita sumar la deriva del GPS estando detenido
HDOP_MAXIMO_DISTANCIA = 5
MAX_BYTES_EVIDENCIA = 10 * 1024 * 1024
DIAS_EVIDENCIA_LOCAL = 3

parar = threading.Event()
sincronizar_ya = threading.Event()
comandos = queue.Queue()


def log(*partes):
    print(time.strftime("%H:%M:%S"), *partes, flush=True)


class Recorrido:
    """Sesion activa. Se guarda en la base para cerrarla si el programa se detiene sin avisar."""

    def __init__(self, db):
        self.db = db
        self.id = None
        self.distancia_m = 0.0
        self._ultima_posicion = None
        self._ultimo_punto = None
        pendiente = almacen.leer_ajuste(db, "sesion_abierta")
        if pendiente:
            almacen.encolar(db, "sesion_fin", dict(
                sesion_id=pendiente["id"], fecha=pendiente["ultima_fecha"],
                distancia_m=pendiente["distancia_m"]))
            almacen.guardar_ajuste(db, "sesion_abierta", None)
            log("Se cerro un recorrido que quedo abierto:", pendiente["id"])

    def _guardar(self, fecha):
        almacen.guardar_ajuste(self.db, "sesion_abierta", dict(
            id=self.id, distancia_m=round(self.distancia_m, 1), ultima_fecha=fecha))

    def iniciar(self):
        self.id = str(uuid.uuid4())
        self.distancia_m = 0.0
        self._ultima_posicion = None
        self._ultimo_punto = None
        fecha = almacen.ahora_utc()
        almacen.encolar(self.db, "sesion_inicio", dict(sesion_id=self.id, fecha=fecha))
        self._guardar(fecha)

    def registrar(self, lectura, ahora):
        if not lectura["valido"]:
            return
        if self._ultimo_punto is not None and ahora - self._ultimo_punto < SEGUNDOS_PUNTO:
            return
        self._ultimo_punto = ahora
        posicion = (lectura["latitud"], lectura["longitud"])
        velocidad = lectura["velocidad_kmh"]
        if (self._ultima_posicion and velocidad is not None
                and velocidad >= VELOCIDAD_MINIMA_DISTANCIA_KMH
                and lectura["hdop"] <= HDOP_MAXIMO_DISTANCIA):
            self.distancia_m += gps.distancia_m(*self._ultima_posicion, *posicion)
        self._ultima_posicion = posicion
        fecha = almacen.ahora_utc()
        almacen.encolar(self.db, "punto", dict(
            sesion_id=self.id, fecha=fecha, latitud=posicion[0], longitud=posicion[1],
            velocidad_kmh=None if velocidad is None else round(velocidad, 1),
            satelites=lectura["satelites"], hdop=lectura["hdop"]))
        self._guardar(fecha)

    def terminar(self):
        almacen.encolar(self.db, "sesion_fin", dict(
            sesion_id=self.id, fecha=almacen.ahora_utc(), distancia_m=round(self.distancia_m, 1)))
        almacen.guardar_ajuste(self.db, "sesion_abierta", None)
        terminado, self.id = self.id, None
        return terminado


def posicion_actual(estado_gps):
    lectura = estado_gps.lectura()
    if not lectura["valido"]:
        return {}
    return dict(latitud=lectura["latitud"], longitud=lectura["longitud"])


def capturar(tipo, ruta):
    if tipo == "foto":
        camara.tomar_foto(ruta)
    elif tipo == "video":
        camara.grabar_video(ruta)
    else:
        raise ValueError("tipo de comando desconocido: " + str(tipo))
    if not ruta.is_file() or ruta.stat().st_size == 0:
        raise RuntimeError("la captura no genero archivo")
    if ruta.stat().st_size > MAX_BYTES_EVIDENCIA:
        raise RuntimeError("el archivo excede 10 MB")


def atender_comando(db, comando, estado_gps, recorrido):
    tipo = comando["tipo"]
    extension = "jpg" if tipo == "foto" else "mp4"
    ruta = EVIDENCIAS / f"{time.strftime('%Y%m%d-%H%M%S')}-{comando['id'][:8]}.{extension}"
    datos = dict(fecha=almacen.ahora_utc(), sesion_id=recorrido.id,
                 comando_id=comando["id"], **posicion_actual(estado_gps))
    log("Capturando", tipo, "por comando", comando["id"])
    try:
        capturar(tipo, ruta)
        almacen.encolar_evidencia(db, ruta, tipo, datos)
        log("Evidencia lista:", ruta.name, ruta.stat().st_size, "bytes")
    except Exception as error:
        ruta.unlink(missing_ok=True)
        almacen.encolar(db, "comando_fallido", dict(comando_id=comando["id"], error=str(error)[:200]))
        log("Fallo la captura:", error)
    sincronizar_ya.set()


ALERTA_POR_RESULTADO = {"no_reconocido": "conductor_no_reconocido",
                        "no_concluyente": "verificacion_no_concluyente"}


def hilo_verificacion(sesion_id, estado_gps):
    db = almacen.abrir(DB)
    try:
        try:
            informe = rostros.verificar_en_camara()
        except Exception as error:
            informe = dict(resultado="no_concluyente", conductor_id=None,
                           motivos={"error": str(error)[:150]})
        resultado = informe["resultado"]
        almacen.encolar(db, "verificacion", dict(
            sesion_id=sesion_id, resultado=resultado,
            conductor_id=informe["conductor_id"] if resultado == "autorizado" else None))
        if resultado in ALERTA_POR_RESULTADO:
            almacen.encolar(db, "alerta", dict(
                sesion_id=sesion_id, tipo=ALERTA_POR_RESULTADO[resultado],
                fecha=almacen.ahora_utc(), **posicion_actual(estado_gps),
                detalle={k: informe.get(k) for k in
                         ("cuadros", "cuadros_con_rostro", "mejor_similitud", "motivos")}))
        log("Verificacion:", resultado, informe)
    finally:
        db.close()
    sincronizar_ya.set()


def limpiar_evidencias(db):
    limite = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - DIAS_EVIDENCIA_LOCAL * 86400))
    for fila in db.execute("SELECT ruta FROM archivos WHERE confirmado IS NOT NULL AND confirmado < ?",
                           (limite,)):
        Path(fila["ruta"]).unlink(missing_ok=True)


def hilo_red(config):
    db = almacen.abrir(DB)
    try:
        while not parar.is_set():
            try:
                for comando in sincronizar.consultar_estado(db, config):
                    log("Comando recibido:", comando["tipo"], comando["id"])
                    comandos.put(comando)
            except Exception as error:
                log("No se pudo consultar el backend:", error)
            try:
                enviados = sincronizar.una_vez(db, config)
                if enviados:
                    log("Sincronizados", enviados, "elementos")
                limpiar_evidencias(db)
            except Exception as error:
                log("Sincronizacion pendiente:", error)
            sincronizar_ya.wait(SEGUNDOS_RED)
            sincronizar_ya.clear()
    finally:
        db.close()


def hilo_camara(estado_gps, recorrido):
    db = almacen.abrir(DB)
    try:
        while not parar.is_set():
            try:
                comando = comandos.get(timeout=1)
            except queue.Empty:
                continue
            atender_comando(db, comando, estado_gps, recorrido)
    finally:
        db.close()


def iniciar_imu():
    try:
        from smbus import SMBus
        bus = SMBus(1)
    except (ImportError, OSError) as error:
        imu = IMU(None)
        imu.fallar(str(error))
        return imu, None
    imu = IMU(bus)
    log("Calibrando giroscopio: no mover el dispositivo...")
    imu.inicializar()
    log("IMU:", imu.error or "calibrada")
    return imu, bus


def probar_camara():
    EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    for tipo, extension in (("foto", "jpg"), ("video", "mp4")):
        ruta = EVIDENCIAS / f"prueba-{tipo}.{extension}"
        inicio = time.monotonic()
        capturar(tipo, ruta)
        log(f"{tipo}: {ruta} ({ruta.stat().st_size} bytes, {time.monotonic() - inicio:.1f} s)")


def main():
    argumentos = argparse.ArgumentParser()
    argumentos.add_argument("--probar-camara", action="store_true",
                            help="toma una foto y un video de prueba y termina")
    if argumentos.parse_args().probar_camara:
        probar_camara()
        return

    config = sincronizar.configurar(CONFIG)
    DB.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    signal.signal(signal.SIGTERM, lambda *_: parar.set())

    db = almacen.abrir(DB)
    estado_gps = gps.EstadoGPS()
    recorrido = Recorrido(db)
    movimiento = DetectorMovimiento()
    exceso = DetectorExceso()
    imu, bus = iniciar_imu()

    hilos = [threading.Thread(target=gps.leer_puerto, args=(estado_gps, parar), daemon=True),
             threading.Thread(target=hilo_red, args=(config,), daemon=True),
             threading.Thread(target=hilo_camara, args=(estado_gps, recorrido), daemon=True)]
    for hilo in hilos:
        hilo.start()
    log("DashGuard v2 en marcha como", config["dispositivo_id"])

    try:
        while not parar.is_set():
            ahora = time.monotonic()
            lectura = estado_gps.lectura()
            evento = movimiento.actualizar(imu.leer(), lectura["velocidad_kmh"], ahora)

            if evento == "inicio":
                recorrido.iniciar()
                exceso = DetectorExceso()
                log("Recorrido iniciado:", recorrido.id)
                threading.Thread(target=hilo_verificacion, args=(recorrido.id, estado_gps),
                                 daemon=True).start()
                sincronizar_ya.set()
            elif evento == "fin":
                log("Recorrido terminado:", recorrido.terminar(), f"{recorrido.distancia_m:.0f} m")
                sincronizar_ya.set()

            if recorrido.id:
                recorrido.registrar(lectura, ahora)
                limite = almacen.leer_ajuste(db, "limite_velocidad_kmh", LIMITE_PREDETERMINADO_KMH)
                if exceso.actualizar(lectura["velocidad_kmh"], limite):
                    almacen.encolar(db, "alerta", dict(
                        sesion_id=recorrido.id, tipo="exceso_velocidad", fecha=almacen.ahora_utc(),
                        **posicion_actual(estado_gps),
                        detalle=dict(velocidad_kmh=round(exceso.maxima_kmh, 1), limite_kmh=limite)))
                    log(f"Alerta: exceso de velocidad {exceso.maxima_kmh:.0f} km/h (limite {limite})")
                    sincronizar_ya.set()

            parar.wait(max(0.0, SEGUNDOS_CICLO - (time.monotonic() - ahora)))
    except KeyboardInterrupt:
        pass
    finally:
        parar.set()
        sincronizar_ya.set()
        if recorrido.id:
            log("Recorrido cerrado al detener:", recorrido.terminar())
        for hilo in hilos[1:]:
            hilo.join(timeout=20)
        db.close()
        if bus:
            bus.close()
        log("DashGuard detenido")


if __name__ == "__main__":
    main()
