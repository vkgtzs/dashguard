import unittest
from prueba_rostros import cadencia, estadistica


class Metricas(unittest.TestCase):
    def test_distingue_hueco_de_fps_nominal(self):
        resultado = cadencia([0, 66_666_667, 133_333_334, 333_333_334])
        self.assertEqual(resultado['huecos_mayores_100ms'], 1)
        self.assertAlmostEqual(resultado['fps'], 9)

    def test_no_inventa_medidas_sin_frames(self):
        self.assertIsNone(cadencia([])['fps'])
        self.assertIsNone(estadistica([]))

    def test_advierte_timestamps_repetidos(self):
        self.assertEqual(cadencia([1, 1])['no_crecientes'], 1)
        self.assertIsNone(cadencia([1, 1])['fps'])


if __name__ == '__main__':
    unittest.main()
