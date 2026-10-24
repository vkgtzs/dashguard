import unittest
from prueba_tiempos import analizar


class Tiempos(unittest.TestCase):
    def test_intervalos_y_hueco(self):
        datos=[{'SensorTimestamp':n} for n in (1000000000,1066666667,1133333334,1266666668)]
        r=analizar(datos,[0,66.666,133.333,266.666])
        self.assertTrue(r['conteos_coinciden'])
        self.assertEqual(r['intervalos_mayores_1_5_mediana'],1)

    def test_faltante_repetido_y_conteos(self):
        with self.assertRaises(ValueError): analizar([{}],[])
        with self.assertRaises(ValueError): analizar([{'SensorTimestamp':1}]*2,[0,1])
        r=analizar([{'SensorTimestamp':1},{'SensorTimestamp':2}],[0])
        self.assertFalse(r['conteos_coinciden'])


if __name__=='__main__': unittest.main()
