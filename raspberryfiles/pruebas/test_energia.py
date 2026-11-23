# Ejecutar desde raspberryfiles/:  python -m unittest discover -s pruebas -t .
import unittest

from energia import ApagadoAutomatico
from imu import DetectorMovimiento


class PruebasApagado(unittest.TestCase):
    def test_apaga_tras_el_tiempo_sin_actividad(self):
        apagado = ApagadoAutomatico(1200, reloj=lambda: 0)
        self.assertFalse(apagado.actualizar(False, False, 1199))
        self.assertTrue(apagado.actualizar(False, False, 1200))

    def test_movimiento_o_recorrido_reinician_el_tiempo(self):
        apagado = ApagadoAutomatico(1200, reloj=lambda: 0)
        self.assertFalse(apagado.actualizar(True, False, 1000))
        self.assertFalse(apagado.actualizar(False, False, 2100))
        self.assertFalse(apagado.actualizar(False, True, 2150))
        self.assertFalse(apagado.actualizar(False, False, 3349))
        self.assertTrue(apagado.actualizar(False, False, 3350))


class PruebasMovimientoESP32(unittest.TestCase):
    def test_usa_la_linea_del_esp(self):
        d = DetectorMovimiento(segundos_inicio=0, segundos_fin=120)
        self.assertIsNone(d.actualizar(dict(imu_valida=True, movimiento=False), None, 0))
        self.assertEqual(d.actualizar(dict(imu_valida=True, movimiento=True), None, 1), "inicio")
        self.assertIsNone(d.actualizar(dict(imu_valida=True, movimiento=False), None, 100))
        self.assertEqual(d.actualizar(dict(imu_valida=True, movimiento=False), None, 121), "fin")

    def test_el_gps_sigue_contando(self):
        d = DetectorMovimiento()
        self.assertTrue(d.hay_movimiento(dict(imu_valida=True, movimiento=False), 30.0))
        self.assertFalse(d.hay_movimiento(dict(imu_valida=True, movimiento=False), 2.0))


if __name__ == "__main__":
    unittest.main()
