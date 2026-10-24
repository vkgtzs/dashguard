import unittest
from video_timestamps import ventanas


class Ventanas(unittest.TestCase):
    def setUp(self):
        self.metadata=[{'SensorTimestamp':1_000_000_000+n*66_666_000} for n in range(6)]
        self.pts=[n*66.666 for n in range(6)]

    def test_particion_sin_solapamiento_y_ultimo_frame(self):
        limites=ventanas(self.metadata,self.pts,[2,3,1])
        self.assertEqual(limites[0]['fin_exclusivo_ns'],limites[1]['inicio_ns'])
        self.assertEqual(limites[1]['fin_exclusivo_ns'],limites[2]['inicio_ns'])
        self.assertEqual(limites[2]['fin_exclusivo_ns'],self.metadata[-1]['SensorTimestamp']+1)
        for i,m in enumerate(self.metadata):
            self.assertEqual(sum(v['inicio_ns']<=m['SensorTimestamp']<v['fin_exclusivo_ns'] for v in limites),1)

    def test_rechaza_conteos_orden_y_desalineacion(self):
        for pts,conteos in [(self.pts,[3,2]),(self.pts[:-1],[3,3]),
                           ([0,66.666,133.332,210,266.664,333.33],[3,3]),
                           ([0,0,133.332,199.998,266.664,333.33],[3,3])]:
            with self.assertRaises(ValueError): ventanas(self.metadata,pts,conteos)
        with self.assertRaises(ValueError): ventanas([{}], [0], [1])


if __name__=='__main__': unittest.main()
