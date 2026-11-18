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
