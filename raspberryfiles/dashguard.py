"""DashGuard v2 en la Raspberry.

- Abre y cierra recorridos segun el movimiento (IMU, o GPS si la IMU falla).
- Registra un punto GPS cada pocos segundos y la distancia recorrida.
- Genera alerta de exceso de velocidad con el limite configurado en la app.
- Verifica el rostro del conductor al iniciar cada recorrido.
- Atiende los comandos de foto, video o registro de rostro que pide el supervisor.
- Mantiene al dia los rostros de los conductores de la cuenta.
- Con el ESP32-C3 conectado, toma de el el movimiento y se apaga sola tras
  20 min sin movimiento (el ESP la vuelve a despertar). Para trabajar en la Pi
  sin que se apague: touch ~/dashguard/config/no_apagar
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
import energia
import gps
import rostros
import sincronizar
from imu import IMU, DetectorMovimiento
from velocidad import DetectorExceso

BASE = Path.home() / "dashguard"
CONFIG = BASE / "config" / "dispositivo.json"
DB = BASE / "datos" / "dashguard-v2.sqlite3"
EVIDENCIAS = BASE / "evidencias"
NO_APAGAR = BASE / "config" / "no_apagar"

# True cuando el MPU-6050 esta en el ESP32-C3; False si sigue conectado a la Pi
USAR_ESP32 = True
MINUTOS_SIN_MOVIMIENTO_PARA_APAGAR = 20

SEGUNDOS_CICLO = 0.5
SEGUNDOS_PUNTO = 5
SEGUNDOS_RED = 10
LIMITE_PREDETERMINADO_KMH = 80
VELOCIDAD_MINIMA_DISTANCIA_KMH = 3   # evita sumar la deriva del GPS estando detenido
# Calidad minima del GPS para guardar un punto y sumar distancia; bajo techo la posicion
# puede saltar decenas o cientos de metros
SATELITES_MINIMOS = 5
HDOP_MAXIMO_DISTANCIA = 3
VELOCIDAD_MAXIMA_CREIBLE_KMH = 160   # un salto mayor entre dos puntos es error del GPS
SALTOS_PARA_REINICIAR = 3            # tras varios saltos seguidos, la posicion anterior era la mala
# Un recorrido es valido si hubo un viaje real; los demas (dispositivo movido en casa,
# GPS a la deriva) se guardan pero se marcan como no validos
DISTANCIA_MINIMA_VALIDA_M = 300
VELOCIDAD_EN_MARCHA_KMH = 10
SEGUNDOS_EN_MARCHA_MINIMOS = 60
# La velocidad del GPS solo cuenta como movimiento con buena senal: bajo techo puede
# marcar 5-10 km/h estando quieto
VELOCIDAD_MOVIMIENTO_KMH = 8
SEGUNDOS_POSICION_ESTACIONADO = 300  # posicion fuera de recorrido, para ver donde quedo el vehiculo
SEGUNDOS_BATERIA = 30
BATERIA_ALERTA = 20                  # %, sin cargador: alerta en la app
BATERIA_APAGADO = 10                 # %, sin cargador: cierra todo y se apaga
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
        self._reiniciar()
        pendiente = almacen.leer_ajuste(db, "sesion_abierta")
        if pendiente:
            self.distancia_m = pendiente["distancia_m"]
            self.segundos_en_marcha = pendiente.get("segundos_en_marcha", 0)
            almacen.encolar(db, "sesion_fin", dict(
                sesion_id=pendiente["id"], fecha=pendiente["ultima_fecha"],
                distancia_m=self.distancia_m, valido=self.es_valido()))
            almacen.guardar_ajuste(db, "sesion_abierta", None)
            log("Se cerro un recorrido que quedo abierto:", pendiente["id"])
            self._reiniciar()

    def _reiniciar(self):
        self.distancia_m = 0.0
        self.segundos_en_marcha = 0.0
        self._ultima_posicion = None   # (latitud, longitud, instante)
        self._ultimo_punto = None
        self._instante_anterior = None
        self._saltos = 0

    def _guardar(self, fecha):
        almacen.guardar_ajuste(self.db, "sesion_abierta", dict(
            id=self.id, distancia_m=round(self.distancia_m, 1),
            segundos_en_marcha=round(self.segundos_en_marcha), ultima_fecha=fecha))

    def es_valido(self):
        return (self.distancia_m >= DISTANCIA_MINIMA_VALIDA_M
                and self.segundos_en_marcha >= SEGUNDOS_EN_MARCHA_MINIMOS)

    def iniciar(self):
        self.id = str(uuid.uuid4())
        self._reiniciar()
        fecha = almacen.ahora_utc()
        almacen.encolar(self.db, "sesion_inicio", dict(sesion_id=self.id, fecha=fecha))
        self._guardar(fecha)

    def registrar(self, lectura, ahora):
        if not lectura["valido"]:
            self._instante_anterior = None
            return
        velocidad = lectura["velocidad_kmh"]
        buena = (lectura["satelites"] >= SATELITES_MINIMOS
                 and lectura["hdop"] <= HDOP_MAXIMO_DISTANCIA)

        # tiempo en marcha: se mide en cada ciclo, no solo cuando se guarda un punto
        if (buena and self._instante_anterior is not None and velocidad is not None
                and velocidad >= VELOCIDAD_EN_MARCHA_KMH):
            self.segundos_en_marcha += min(ahora - self._instante_anterior, 2.0)
        self._instante_anterior = ahora

        if self._ultimo_punto is not None and ahora - self._ultimo_punto < SEGUNDOS_PUNTO:
            return
        self._ultimo_punto = ahora
        if not buena:
            return

        posicion = (lectura["latitud"], lectura["longitud"])
        if self._ultima_posicion:
            latitud, longitud, instante = self._ultima_posicion
            paso = gps.distancia_m(latitud, longitud, *posicion)
            implicita_kmh = paso / max(ahora - instante, 0.001) * 3.6
            # salto: mas rapido de lo creible, o mucho mas rapido de lo que el GPS dice que vamos
            salto = (implicita_kmh > VELOCIDAD_MAXIMA_CREIBLE_KMH
                     or (velocidad is not None and implicita_kmh > 2 * velocidad + 30))
            if salto:
                self._saltos += 1
                if self._saltos < SALTOS_PARA_REINICIAR:
                    return  # posicion imposible: se descarta
                # varias seguidas lejos de la anterior: la equivocada era la anterior
                self._ultima_posicion = None
            elif velocidad is not None and velocidad >= VELOCIDAD_MINIMA_DISTANCIA_KMH:
                self.distancia_m += paso
        self._saltos = 0
        self._ultima_posicion = (*posicion, ahora)

        fecha = almacen.ahora_utc()
        almacen.encolar(self.db, "punto", dict(
            sesion_id=self.id, fecha=fecha, latitud=posicion[0], longitud=posicion[1],
            velocidad_kmh=None if velocidad is None else round(velocidad, 1),
            satelites=lectura["satelites"], hdop=lectura["hdop"]))
        self._guardar(fecha)

    def terminar(self):
        valido = self.es_valido()
        almacen.encolar(self.db, "sesion_fin", dict(
            sesion_id=self.id, fecha=almacen.ahora_utc(), distancia_m=round(self.distancia_m, 1),
            valido=valido))
        almacen.guardar_ajuste(self.db, "sesion_abierta", None)
        terminado, self.id = self.id, None
        if not valido:
            log(f"Recorrido sin viaje real ({self.distancia_m:.0f} m, "
                f"{self.segundos_en_marcha:.0f} s en marcha): se marca como no valido")
        return terminado


def senal_buena(lectura):
    return (lectura["valido"] and lectura["satelites"] >= SATELITES_MINIMOS
            and lectura["hdop"] <= HDOP_MAXIMO_DISTANCIA)


def velocidad_confiable(lectura):
    """Velocidad del GPS solo si la senal es buena; None si no se debe usar."""
    return lectura["velocidad_kmh"] if senal_buena(lectura) else None


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


def registrar_rostro(db, comando):
    log("Registrando rostro del conductor", comando.get("conductor_id"))
    try:
        if not comando.get("conductor_id"):
            raise ValueError("el comando no indica el conductor")
        descriptores = rostros.capturar_muestras(aviso=lambda texto: log(texto.strip()))
        almacen.encolar(db, "rostro", dict(conductor_id=comando["conductor_id"],
                                           comando_id=comando["id"], descriptores=descriptores))
        log("Rostro registrado; se enviara al servidor")
    except Exception as error:
        almacen.encolar(db, "comando_fallido", dict(comando_id=comando["id"], error=str(error)[:200]))
        log("Fallo el registro de rostro:", error)
    sincronizar_ya.set()


def atender_comando(db, comando, estado_gps, recorrido):
    tipo = comando["tipo"]
    if tipo == "registro_rostro":
        registrar_rostro(db, comando)
        return
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
    limite = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                           time.gmtime(almacen.ahora_epoch() - DIAS_EVIDENCIA_LOCAL * 86400))
    for fila in db.execute("SELECT ruta FROM archivos WHERE confirmado IS NOT NULL AND confirmado < ?",
                           (limite,)):
        Path(fila["ruta"]).unlink(missing_ok=True)


bateria_actual = None  # ultima lectura del UPS; la escribe el ciclo principal y la envia hilo_red


def hilo_red(config):
    db = almacen.abrir(DB)
    try:
        while not parar.is_set():
            # Primero se envia lo pendiente (incluidos rostros nuevos) y despues se
            # descarga el estado, para no reemplazar un rostro antes de subirlo.
            try:
                enviados = sincronizar.una_vez(db, config)
                if enviados:
                    log("Sincronizados", enviados, "elementos")
                limpiar_evidencias(db)
            except Exception as error:
                log("Sincronizacion pendiente:", error)
            try:
                for comando in sincronizar.consultar_estado(db, config, bateria=bateria_actual):
                    log("Comando recibido:", comando["tipo"], comando["id"])
                    comandos.put(comando)
                if sincronizar.sincronizar_rostros(db, config):
                    log("Rostros de conductores actualizados:", len(rostros.cargar_conductores()))
            except Exception as error:
                log("No se pudo consultar el backend:", error)
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
    global bateria_actual
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
    almacen.usar_hora_gps(estado_gps.hora_utc)
    reloj_revisado = False
    recorrido = Recorrido(db)
    movimiento = DetectorMovimiento(velocidad_min_kmh=VELOCIDAD_MOVIMIENTO_KMH)
    exceso = DetectorExceso()
    esp32, bus, fuente = None, None, None
    if USAR_ESP32:
        try:
            esp32 = fuente = energia.EnlaceESP32()
            log("Movimiento desde el ESP32-C3")
        except Exception as error:
            log("ESP32-C3 no disponible, se usa el MPU de la Pi:", error)
    if fuente is None:
        fuente, bus = iniciar_imu()
    apagado = energia.ApagadoAutomatico(MINUTOS_SIN_MOVIMIENTO_PARA_APAGAR * 60)
    apagar = False
    try:
        medidor = energia.Bateria()
    except Exception as error:
        medidor = None
        log("Sin lectura de bateria:", error)
    vigilante = energia.VigilanteBateria(BATERIA_ALERTA, BATERIA_APAGADO,
                                         alerta_enviada=almacen.leer_ajuste(db, "bateria_alerta_enviada", False))
    ultima_bateria = ultima_posicion = None

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
            if not reloj_revisado and (desfase := almacen.desfase_reloj()) is not None:
                reloj_revisado = True
                if abs(desfase) > almacen.DESFASE_MAXIMO_S:
                    log(f"Reloj del sistema desfasado {desfase:+.0f} s; se usa la hora del GPS")
                else:
                    log("Reloj del sistema coincide con el GPS")
            muestra = fuente.leer()
            velocidad = velocidad_confiable(lectura)
            evento = movimiento.actualizar(muestra, velocidad, ahora)

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

            # posicion con el vehiculo estacionado: al tener senal y luego cada 5 min
            if (not recorrido.id and senal_buena(lectura) and
                    (ultima_posicion is None or ahora - ultima_posicion >= SEGUNDOS_POSICION_ESTACIONADO)):
                almacen.encolar(db, "posicion", dict(
                    fecha=almacen.ahora_utc(), latitud=lectura["latitud"], longitud=lectura["longitud"],
                    velocidad_kmh=lectura["velocidad_kmh"]))
                if ultima_posicion is None:
                    log("Posicion GPS disponible; se reporta con el vehiculo estacionado")
                    sincronizar_ya.set()
                ultima_posicion = ahora

            if medidor and (ultima_bateria is None or ahora - ultima_bateria >= SEGUNDOS_BATERIA):
                ultima_bateria = ahora
                medida = medidor.leer()
                if medida:
                    if bateria_actual is None:
                        log(f"Bateria {medida['porcentaje']} % ({medida['voltaje']} V)",
                            "cargando" if medida["cargando"] else "sin cargador")
                    bateria_actual = medida
                    accion = vigilante.actualizar(medida["porcentaje"], medida["cargando"])
                    if accion in ("alerta", "rearmar"):
                        almacen.guardar_ajuste(db, "bateria_alerta_enviada", vigilante.alerta_enviada)
                    if accion == "alerta":
                        almacen.encolar(db, "alerta", dict(
                            sesion_id=recorrido.id, tipo="bateria_baja", fecha=almacen.ahora_utc(),
                            **posicion_actual(estado_gps),
                            detalle=dict(porcentaje=medida["porcentaje"], voltaje=medida["voltaje"])))
                        log(f"Alerta: bateria baja {medida['porcentaje']} %")
                        sincronizar_ya.set()
                    elif accion == "apagar":
                        # no se respeta no_apagar: sin bateria la Pi se apagaria de golpe
                        log(f"Bateria al {medida['porcentaje']} % sin cargador: apagado seguro")
                        apagar = True
                        break

            if esp32 and apagado.actualizar(movimiento.hay_movimiento(muestra, velocidad),
                                            recorrido.id is not None, ahora):
                if NO_APAGAR.exists():
                    apagado = energia.ApagadoAutomatico(apagado.segundos)
                else:
                    log(f"{MINUTOS_SIN_MOVIMIENTO_PARA_APAGAR} min sin movimiento: apagando la Raspberry")
                    apagar = True
                    break

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
        try:
            # ultimo intento de enviar lo pendiente, incluido el cierre del recorrido
            if sincronizar.una_vez(db, config):
                log("Pendientes enviados antes de detener")
        except Exception as error:
            log("Quedan datos pendientes; se enviaran al volver a encender:", error)
        db.close()
        if bus:
            bus.close()
        if medidor:
            medidor.cerrar()
        if esp32:
            esp32.cerrar()
        log("DashGuard detenido")
        if apagar:
            try:
                energia.apagar_raspberry()
            except Exception as error:
                log("No se pudo apagar; revisa /etc/sudoers.d/dashguard-apagado:", error)


if __name__ == "__main__":
    main()
