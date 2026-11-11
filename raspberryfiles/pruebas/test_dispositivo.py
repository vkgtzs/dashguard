# Ejecutar desde raspberryfiles/:  python -m unittest discover -s pruebas -t .
import io
import json
import tempfile
import unittest
from pathlib import Path

import almacen
import sincronizar
from gps import EstadoGPS, campos_nmea, coordenada, distancia_m
from imu import GRAVEDAD, DetectorMovimiento
from velocidad import DetectorExceso


def nmea(cuerpo):
    suma = 0
    for caracter in cuerpo:
        suma ^= ord(caracter)
    return f"${cuerpo}*{suma:02X}"


GGA = nmea("GPGGA,123519,1925.9580,N,09907.9920,W,1,08,0.9,2240.0,M,0,M,,")
RMC = nmea("GPRMC,123519,A,1925.9580,N,09907.9920,W,54.0,084.4,230394,003.1,W")


class PruebasGPS(unittest.TestCase):
    def test_coordenada(self):
        self.assertAlmostEqual(coordenada("1925.9580", "N", True), 19.4326333, places=6)
        self.assertAlmostEqual(coordenada("09907.9920", "W", False), -99.1332, places=6)
        with self.assertRaises(ValueError):
            coordenada("9100.0", "N", True)

    def test_checksum_incorrecto(self):
        with self.assertRaises(ValueError):
            campos_nmea(GGA[:-2] + "00")

    def test_posicion_y_velocidad(self):
        estado = EstadoGPS(reloj=lambda: 0)
        estado.procesar(GGA)
        estado.procesar(RMC)
        lectura = estado.lectura()
        self.assertTrue(lectura["valido"])
        self.assertEqual(lectura["satelites"], 8)
        self.assertAlmostEqual(lectura["velocidad_kmh"], 54 * 1.852)

    def test_lectura_caduca(self):
        instante = [0]
        estado = EstadoGPS(reloj=lambda: instante[0])
        estado.procesar(GGA)
        instante[0] = 11
        self.assertFalse(estado.lectura()["valido"])

    def test_sin_fix_invalida_la_posicion(self):
        estado = EstadoGPS(reloj=lambda: 0)
        estado.procesar(GGA)
        estado.procesar(nmea("GPGGA,123520,,,,,0,00,,,M,,M,,"))
        self.assertFalse(estado.lectura()["valido"])

    def test_basura_se_ignora(self):
        estado = EstadoGPS(reloj=lambda: 0)
        estado.procesar("esto no es NMEA")
        self.assertFalse(estado.lectura()["valido"])

    def test_distancia(self):
        # Un grado de latitud mide unos 111.2 km.
        self.assertAlmostEqual(distancia_m(19, -99, 20, -99), 111195, delta=50)
        self.assertEqual(distancia_m(19, -99, 19, -99), 0)


class PruebasVelocidad(unittest.TestCase):
    def test_tres_lecturas_seguidas(self):
        detector = DetectorExceso()
        self.assertEqual([detector.actualizar(v, 80) for v in (85, 90, 88, 95)],
                         [False, False, True, False])
        self.assertEqual(detector.maxima_kmh, 95)

    def test_una_lectura_normal_reinicia(self):
        detector = DetectorExceso()
        self.assertEqual([detector.actualizar(v, 80) for v in (85, 90, 80, 85, 90)],
                         [False] * 5)

    def test_lectura_sin_velocidad_se_ignora(self):
        detector = DetectorExceso()
        self.assertEqual([detector.actualizar(v, 80) for v in (85, None, 90, 88)],
                         [False, False, False, True])

    def test_rearma_tras_bajar(self):
        detector = DetectorExceso()
        resultados = [detector.actualizar(v, 80) for v in (90, 90, 90, 70, 90, 90, 90)]
        self.assertEqual(resultados.count(True), 2)


class PruebasMovimiento(unittest.TestCase):
    QUIETO = dict(imu_valida=True, magnitud_ms2=GRAVEDAD, gx_grados_s=0, gy_grados_s=0, gz_grados_s=0)
    MOVIDO = dict(QUIETO, magnitud_ms2=GRAVEDAD + 1.5)

    def test_inicio_requiere_movimiento_sostenido(self):
        d = DetectorMovimiento(segundos_inicio=3)
        self.assertIsNone(d.actualizar(self.MOVIDO, None, 0))
        self.assertIsNone(d.actualizar(self.QUIETO, None, 1))
        self.assertIsNone(d.actualizar(self.MOVIDO, None, 2))
        self.assertIsNone(d.actualizar(self.MOVIDO, None, 4))
        self.assertEqual(d.actualizar(self.MOVIDO, None, 5), "inicio")

    def test_fin_tras_reposo_largo(self):
        d = DetectorMovimiento(segundos_inicio=0, segundos_fin=120)
        self.assertEqual(d.actualizar(self.MOVIDO, None, 0), "inicio")
        self.assertIsNone(d.actualizar(self.QUIETO, None, 60))
        self.assertIsNone(d.actualizar(self.QUIETO, 30.0, 100))
        self.assertIsNone(d.actualizar(self.QUIETO, None, 200))
        self.assertEqual(d.actualizar(self.QUIETO, None, 220), "fin")
        self.assertFalse(d.en_sesion)

    def test_imu_invalida_usa_gps(self):
        d = DetectorMovimiento(segundos_inicio=0)
        invalida = dict(imu_valida=False)
        self.assertIsNone(d.actualizar(invalida, None, 0))
        self.assertEqual(d.actualizar(invalida, 20.0, 1), "inicio")


class RespuestaFalsa(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class PruebasColaYSincronizacion(unittest.TestCase):
    CONFIG = dict(backend="https://ejemplo.invalid", dispositivo_id="pi-1", token="t" * 40)

    def setUp(self):
        self.carpeta = tempfile.TemporaryDirectory()
        self.db = almacen.abrir(Path(self.carpeta.name) / "datos.sqlite3")
        self.peticiones = []

    def tearDown(self):
        self.db.close()
        self.carpeta.cleanup()

    def servidor(self, peticion, timeout):
        self.peticiones.append(peticion)
        if peticion.get_method() == "PUT":
            cuerpo = dict(id=peticion.full_url.rsplit("/", 1)[1],
                          sha256=peticion.get_header("X-content-sha256"))
        else:
            cuerpo = dict(confirmados=[r["id"] for r in json.loads(peticion.data)["registros"]])
        return RespuestaFalsa(json.dumps(cuerpo).encode())

    def sin_red(self, peticion, timeout):
        raise OSError("sin red")

    def test_registros_en_orden_y_sin_reenvio(self):
        almacen.encolar(self.db, "sesion_inicio", dict(sesion_id="s", fecha="2026-11-11T00:00:00Z"))
        almacen.encolar(self.db, "punto", dict(sesion_id="s", latitud=19.4, longitud=-99.1))
        self.assertEqual(sincronizar.una_vez(self.db, self.CONFIG, self.servidor), 2)
        enviados = json.loads(self.peticiones[0].data)["registros"]
        self.assertEqual([r["tipo"] for r in enviados], ["sesion_inicio", "punto"])
        self.assertEqual(sincronizar.una_vez(self.db, self.CONFIG, self.servidor), 0)
        self.assertEqual(len(self.peticiones), 1)

    def test_sin_red_conserva_pendientes(self):
        almacen.encolar(self.db, "punto", dict(sesion_id="s"))
        with self.assertRaises(OSError):
            sincronizar.una_vez(self.db, self.CONFIG, self.sin_red)
        self.assertEqual(len(almacen.registros_pendientes(self.db)), 1)
        self.assertEqual(sincronizar.una_vez(self.db, self.CONFIG, self.servidor), 1)

    def test_evidencia_espera_a_su_archivo(self):
        foto = Path(self.carpeta.name) / "foto.jpg"
        foto.write_bytes(b"\xff\xd8 contenido de prueba")
        identificador = almacen.encolar_evidencia(self.db, foto, "foto", dict(fecha="2026-11-11T00:00:00Z"))
        self.assertEqual(almacen.registros_pendientes(self.db), [])
        self.assertEqual(sincronizar.una_vez(self.db, self.CONFIG, self.servidor), 2)
        self.assertEqual(self.peticiones[0].get_method(), "PUT")
        self.assertTrue(self.peticiones[0].full_url.endswith("/dispositivo/evidencias/" + identificador))
        ficha = json.loads(self.peticiones[1].data)["registros"][0]["datos"]
        self.assertEqual(ficha["evidencia_id"], identificador)
        self.assertEqual(ficha["sha256"], almacen.sha_archivo(foto))

    def test_rechazado_no_bloquea_la_cola(self):
        malo = almacen.encolar(self.db, "punto", dict(sesion_id="inexistente"))
        bueno = almacen.encolar(self.db, "punto", dict(sesion_id="s"))

        def servidor(peticion, timeout):
            return RespuestaFalsa(json.dumps(dict(
                confirmados=[bueno], rechazados=[dict(id=malo, motivo="sesion desconocida")])).encode())
        self.assertEqual(sincronizar.una_vez(self.db, self.CONFIG, servidor), 1)
        self.assertEqual(almacen.registros_pendientes(self.db), [])
        motivo = self.db.execute("SELECT rechazo FROM cola WHERE id=?", (malo,)).fetchone()[0]
        self.assertEqual(motivo, "sesion desconocida")

    def test_comando_solo_una_vez(self):
        def estado(peticion, timeout):
            return RespuestaFalsa(json.dumps(dict(limite_velocidad_kmh=60, conductores=[],
                                                  comandos=[dict(id="c1", tipo="foto")])).encode())
        self.assertEqual(len(sincronizar.consultar_estado(self.db, self.CONFIG, estado)), 1)
        self.assertEqual(sincronizar.consultar_estado(self.db, self.CONFIG, estado), [])
        self.assertEqual(almacen.leer_ajuste(self.db, "limite_velocidad_kmh"), 60)

    def test_backend_debe_ser_https(self):
        ruta = Path(self.carpeta.name) / "dispositivo.json"
        ruta.write_text(json.dumps(dict(self.CONFIG, backend="http://ejemplo.invalid")))
        with self.assertRaises(ValueError):
            sincronizar.configurar(ruta)


if __name__ == "__main__":
    unittest.main()
