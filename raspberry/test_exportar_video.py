import unittest
from exportar_video import ultima_secuencia, metadatos_segmento


class Exportacion(unittest.TestCase):
    def test_orden_temporal_no_uuid_y_no_mezclar_sesiones(self):
        filas=[dict(id='z',boot_id='anterior',inicio_ns=0,fin_ns=10),
               dict(id='b',boot_id='nuevo',inicio_ns=20,fin_ns=30),
               dict(id='a',boot_id='nuevo',inicio_ns=30,fin_ns=40)]
        self.assertEqual([r['id'] for r in ultima_secuencia(filas)],['b','a'])
        filas[1]['fin_ns']=29
        self.assertEqual(len(ultima_secuencia(filas)),1)

    def test_ajuste_timeline_y_validacion(self):
        datos=dict(video_id='uuid',archivo='uuid.mp4',inicio_ns=100,fin_exclusivo_ns=301,
            sensor_timestamps_ns=[100,200,300],pts_originales_ms=[0,100,200],
            muestras=[dict(muestra_id='m',boottime_ns=250,datos={})])
        info=dict(avg_frame_rate='10/1',nb_read_frames='3',duration='0.3')
        meta,duracion=metadatos_segmento(datos,info,5)
        self.assertAlmostEqual(duracion,0.3)
        self.assertAlmostEqual(meta['muestras'][0]['tiempo_video_s_aproximado'],5.1)
        self.assertEqual(meta['muestras'][0]['boottime_ns'],250)
        with self.assertRaises(ValueError): metadatos_segmento(datos,{**info,'nb_read_frames':'2'},0)


if __name__=='__main__': unittest.main()
