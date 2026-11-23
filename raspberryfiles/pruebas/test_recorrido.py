# Ejecutar desde raspberryfiles/:  python -m unittest discover -s pruebas -t .
import json
import tempfile
import unittest
from pathlib import Path

import almacen
import dashguard

# ~1 m de latitud en grados
METRO = 1 / 111195


def lectura(latitud, velocidad, satelites=8, hdop=1.0, longitud=-117.0):
    return dict(valido=True, latitud=latitud, longitud=longitud, velocidad_kmh=velocidad,
                satelites=satelites, hdop=hdop)


class PruebasRecorrido(unittest.TestCase):
    def setUp(self):
        self.carpeta = tempfile.TemporaryDirectory()
        self.db = almacen.abrir(Path(self.carpeta.name) / "d.sqlite3")
        self.recorrido = dashguard.Recorrido(self.db)
        self.recorrido.iniciar()

    def tearDown(self):
        self.db.close()
        self.carpeta.cleanup()

    def cierre(self):
        self.recorrido.terminar()
        fila = self.db.execute("select datos_json from cola where tipo='sesion_fin'").fetchone()
        return json.loads(fila[0])

    def puntos(self):
        return self.db.execute("select count(*) from cola where tipo='punto'").fetchone()[0]

    def test_viaje_real_es_valido(self):
        # 3 minutos a ~36 km/h (10 m/s), una lectura cada 0.5 s
        for i in range(360):
            t = i * 0.5
            self.recorrido.registrar(lectura(32.5 + 10 * t * METRO, 36.0), t)
        datos = self.cierre()
        self.assertTrue(datos["valido"])
        self.assertAlmostEqual(datos["distancia_m"], 1795, delta=60)

    def test_en_casa_con_salto_del_gps_no_es_valido(self):
        lecturas = [lectura(32.5, 0.5)] * 20 + [lectura(32.5 + 170 * METRO, 25.0)] + [lectura(32.5, 0.8)] * 40
        for i, l in enumerate(lecturas):
            self.recorrido.registrar(l, i * 0.5)
        datos = self.cierre()
        self.assertFalse(datos["valido"])
        self.assertLess(datos["distancia_m"], 20)

    def test_poca_senal_no_guarda_puntos_ni_distancia(self):
        for i in range(200):
            self.recorrido.registrar(lectura(32.5 + i * 5 * METRO, 36.0, satelites=4), i * 0.5)
        self.assertEqual(self.puntos(), 0)
        self.assertEqual(self.cierre()["distancia_m"], 0)

    def test_tres_saltos_seguidos_reinician_la_posicion(self):
        # la primera posicion era la equivocada: el GPS se queda en otro lugar
        self.recorrido.registrar(lectura(32.5, 20.0), 0)
        for i in range(1, 6):
            self.recorrido.registrar(lectura(32.5 + 2000 * METRO, 20.0), i * 5)
        self.assertEqual(self.puntos(), 1 + 3)
        self.assertLess(self.recorrido.distancia_m, 1)

    def test_cierre_tras_apagon_conserva_la_calificacion(self):
        for i in range(360):
            t = i * 0.5
            self.recorrido.registrar(lectura(32.5 + 10 * t * METRO, 36.0), t)
        recuperado = dashguard.Recorrido(self.db)  # simula reinicio con el recorrido abierto
        self.assertIsNone(recuperado.id)
        fila = self.db.execute("select datos_json from cola where tipo='sesion_fin'").fetchone()
        self.assertTrue(json.loads(fila[0])["valido"])


if __name__ == "__main__":
    unittest.main()
