# Ejecutar desde raspberryfiles/:  python -m unittest discover -s pruebas -t .
import calendar
import time
import unittest

import almacen
from gps import EstadoGPS, hora_rmc


def nmea(cuerpo):
    suma = 0
    for caracter in cuerpo:
        suma ^= ord(caracter)
    return f"${cuerpo}*{suma:02X}"


# 18 de noviembre de 2026, 16:30:05.50 UTC
RMC_2026 = nmea("GPRMC,163005.50,A,3231.0000,N,11701.0000,W,0.0,0.0,181126,,,A")
EPOCA_2026 = calendar.timegm((2026, 11, 18, 16, 30, 5, 0, 0, 0)) + 0.5


class PruebasHoraGPS(unittest.TestCase):
    def test_hora_rmc(self):
        self.assertEqual(hora_rmc("163005.50", "181126"), EPOCA_2026)

    def test_fechas_invalidas(self):
        with self.assertRaises(ValueError):
            hora_rmc("163005", "180306")  # 2006: reinicio de semana del NEO-6M viejo
        with self.assertRaises(ValueError):
            hora_rmc("253005", "181126")
        with self.assertRaises(ValueError):
            hora_rmc("", "")

    def test_hora_avanza_con_el_reloj_monotonico(self):
        instante = [100.0]
        estado = EstadoGPS(reloj=lambda: instante[0])
        self.assertIsNone(estado.hora_utc())
        estado.procesar(RMC_2026)
        instante[0] = 160.0
        self.assertAlmostEqual(estado.hora_utc(), EPOCA_2026 + 60)

    def test_sin_fix_no_da_hora(self):
        estado = EstadoGPS(reloj=lambda: 0)
        estado.procesar(nmea("GPRMC,163005.50,V,,,,,,,181126,,,N"))
        self.assertIsNone(estado.hora_utc())


class PruebasRelojDelSistema(unittest.TestCase):
    def tearDown(self):
        almacen.usar_hora_gps(None)

    def test_sin_gps_usa_el_sistema(self):
        almacen.usar_hora_gps(None)
        self.assertAlmostEqual(almacen.ahora_epoch(), time.time(), delta=1)

    def test_desfase_pequeno_usa_el_sistema(self):
        almacen.usar_hora_gps(lambda: time.time() - 1)
        self.assertAlmostEqual(almacen.ahora_epoch(), time.time(), delta=0.5)

    def test_reloj_atrasado_usa_el_gps(self):
        dentro_de_un_dia = time.time() + 86400
        almacen.usar_hora_gps(lambda: dentro_de_un_dia)
        self.assertAlmostEqual(almacen.desfase_reloj(), -86400, delta=1)
        self.assertAlmostEqual(almacen.ahora_epoch(), dentro_de_un_dia, delta=1)
        esperado = time.strftime("%Y-%m-%d", time.gmtime(dentro_de_un_dia))
        self.assertTrue(almacen.ahora_utc().startswith(esperado))


if __name__ == "__main__":
    unittest.main()
