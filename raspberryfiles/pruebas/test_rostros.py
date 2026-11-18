# Ejecutar desde raspberryfiles/:  python -m unittest discover -s pruebas -t .
import unittest

import rostros
from rostros import decidir, mejor_coincidencia, similitud, verificar

A, B = "aaaaaaaa-0000-4000-8000-000000000001", "bbbbbbbb-0000-4000-8000-000000000002"


class RostrosFalsos:
    """Devuelve una secuencia fija: None = sin rostro, lista = descriptor."""

    def __init__(self, secuencia):
        self.secuencia = iter(secuencia)
        self.actual = None

    def cara_principal(self, imagen):
        self.actual = next(self.secuencia, None)
        return (None, "sin_rostro") if self.actual is None else ("cara", None)

    def descriptor(self, imagen, cara):
        return self.actual


class RelojFalso:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def esperar(self, s):
        self.t += s


CONDUCTORES = {A: dict(nombre="A", descriptores=[[1.0, 0.0, 0.0]]),
               B: dict(nombre="B", descriptores=[[0.0, 1.0, 0.0]])}


class PruebasDecision(unittest.TestCase):
    def test_similitud(self):
        self.assertAlmostEqual(similitud([1, 0], [1, 0]), 1.0)
        self.assertAlmostEqual(similitud([1, 0], [0, 1]), 0.0)
        self.assertEqual(similitud([0, 0], [1, 0]), 0.0)

    def test_mejor_coincidencia(self):
        conductor, valor = mejor_coincidencia([0.1, 0.9, 0.0], CONDUCTORES)
        self.assertEqual(conductor, B)
        self.assertGreater(valor, 0.9)

    def test_autorizado_con_tres_coincidencias(self):
        self.assertEqual(decidir([(A, 0.6)] * 2), ("no_concluyente", None))
        self.assertEqual(decidir([(A, 0.6)] * 3), ("autorizado", A))

    def test_coincidencias_repartidas_no_autorizan(self):
        self.assertEqual(decidir([(A, 0.6), (B, 0.6), (A, 0.6), (B, 0.6)])[0], "no_concluyente")

    def test_no_reconocido_requiere_cinco_claros(self):
        self.assertEqual(decidir([(A, 0.1)] * 4)[0], "no_concluyente")
        self.assertEqual(decidir([(A, 0.1)] * 5), ("no_reconocido", None))

    def test_zona_dudosa_es_no_concluyente(self):
        self.assertEqual(decidir([(A, 0.3)] * 10)[0], "no_concluyente")

    def test_una_coincidencia_impide_no_reconocido(self):
        self.assertEqual(decidir([(A, 0.1)] * 6 + [(A, 0.5)])[0], "no_concluyente")


class PruebasVerificar(unittest.TestCase):
    def ejecutar(self, secuencia, segundos=30):
        reloj = RelojFalso()
        return verificar(RostrosFalsos(secuencia), CONDUCTORES, lambda: "imagen",
                         segundos=segundos, pausa=1, reloj=reloj, esperar=reloj.esperar)

    def test_reconoce_y_termina_pronto(self):
        informe = self.ejecutar([None, None, [0.9, 0.1, 0], [1, 0, 0], [0.95, 0.05, 0], [1, 0, 0]])
        self.assertEqual((informe["resultado"], informe["conductor_id"]), ("autorizado", A))
        self.assertEqual(informe["cuadros"], 5)
        self.assertEqual(informe["motivos"], {"sin_rostro": 2})

    def test_sin_rostro_es_no_concluyente(self):
        informe = self.ejecutar([None] * 100, segundos=10)
        self.assertEqual(informe["resultado"], "no_concluyente")
        self.assertEqual(informe["cuadros_con_rostro"], 0)
        self.assertEqual(informe["cuadros"], 10)

    def test_desconocido(self):
        informe = self.ejecutar([[0, 0, 1]] * 6)
        self.assertEqual(informe["resultado"], "no_reconocido")

    def test_sin_conductores_no_abre_la_camara(self):
        from pathlib import Path
        informe = rostros.verificar_en_camara(Path("/no/existe.json"))
        self.assertEqual(informe["resultado"], "no_concluyente")
        self.assertIn("sin_conductores_registrados", informe["motivos"])


if __name__ == "__main__":
    unittest.main()


class PruebasSincronizacionRostros(unittest.TestCase):
    CONFIG = dict(backend="https://ejemplo.invalid", dispositivo_id="pi-1", token="t" * 40)

    def setUp(self):
        import tempfile
        from pathlib import Path
        import almacen
        self.almacen = almacen
        self.carpeta = tempfile.TemporaryDirectory()
        self.ruta = Path(self.carpeta.name) / "conductores.json"
        self.db = almacen.abrir(Path(self.carpeta.name) / "datos.sqlite3")
        self.descargas = 0
        self.servidor_rostros = [dict(id=A, nombre="A", descriptores=[[1.0, 0.0]], rostro_actualizado="t1")]

    def tearDown(self):
        self.db.close()
        self.carpeta.cleanup()

    def servidor(self, peticion, timeout):
        import io
        import json

        class Respuesta(io.BytesIO):
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_):
                self.close()
        self.descargas += 1
        return Respuesta(json.dumps(dict(conductores=self.servidor_rostros)).encode())

    def sincronizar(self, conductores):
        import sincronizar
        self.almacen.guardar_ajuste(self.db, "conductores", conductores)
        return sincronizar.sincronizar_rostros(self.db, self.CONFIG, self.servidor, self.ruta)

    def test_descarga_solo_cuando_cambia(self):
        estado = [dict(id=A, nombre="A", rostro_actualizado="t1"), dict(id=B, nombre="B", rostro_actualizado=None)]
        self.assertTrue(self.sincronizar(estado))
        self.assertEqual(list(rostros.cargar_conductores(self.ruta)), [A])
        self.assertFalse(self.sincronizar(estado))
        self.assertEqual(self.descargas, 1)

    def test_conductor_desactivado_se_quita(self):
        self.sincronizar([dict(id=A, nombre="A", rostro_actualizado="t1")])
        self.servidor_rostros = []
        self.assertTrue(self.sincronizar([]))
        self.assertEqual(rostros.cargar_conductores(self.ruta), {})

    def test_sin_red_conserva_los_rostros(self):
        import sincronizar
        self.sincronizar([dict(id=A, nombre="A", rostro_actualizado="t1")])
        self.almacen.guardar_ajuste(self.db, "conductores", [dict(id=A, nombre="A", rostro_actualizado="t2")])

        def sin_red(peticion, timeout):
            raise OSError("sin red")
        with self.assertRaises(OSError):
            sincronizar.sincronizar_rostros(self.db, self.CONFIG, sin_red, self.ruta)
        self.assertEqual(list(rostros.cargar_conductores(self.ruta)), [A])
        self.servidor_rostros[0]["rostro_actualizado"] = "t2"
        self.assertTrue(sincronizar.sincronizar_rostros(self.db, self.CONFIG, self.servidor, self.ruta))
