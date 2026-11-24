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


class PruebasVigilanteBateria(unittest.TestCase):
    def setUp(self):
        from energia import VigilanteBateria
        self.v = VigilanteBateria(20, 10, lecturas=3)

    def leer(self, porcentaje, cargando=False, veces=1):
        return [self.v.actualizar(porcentaje, cargando) for _ in range(veces)][-1]

    def test_alerta_una_vez_tras_lecturas_seguidas(self):
        self.assertIsNone(self.leer(19, veces=2))
        self.assertEqual(self.leer(19), "alerta")
        self.assertIsNone(self.leer(18, veces=5))

    def test_una_lectura_alta_reinicia_la_cuenta(self):
        self.leer(19, veces=2)
        self.leer(21)
        self.assertIsNone(self.leer(19, veces=2))

    def test_apaga_al_10_sin_cargador(self):
        self.assertIsNone(self.leer(9, veces=2))
        self.assertEqual(self.leer(9), "apagar")

    def test_con_cargador_no_avisa_ni_apaga(self):
        self.assertIsNone(self.leer(5, cargando=True, veces=10))

    def test_cargar_rearma_la_alerta(self):
        self.leer(15, veces=3)
        self.assertEqual(self.leer(15, cargando=True), "rearmar")
        self.assertEqual(self.leer(15, veces=3), "alerta")

    def test_recuerda_alerta_enviada_antes_de_reiniciar(self):
        from energia import VigilanteBateria
        v = VigilanteBateria(20, 10, lecturas=3, alerta_enviada=True)
        self.assertIsNone([v.actualizar(15, False) for _ in range(3)][-1])
