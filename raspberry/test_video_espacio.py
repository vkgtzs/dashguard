import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from video_espacio import ObjetosJSON, esquema, ocupacion, ajustar_cuota, validar_tiempos


class Tiempos(unittest.TestCase):
    def test_metadata_en_chunks_y_objetos_sin_array(self):
        for texto in ('[{"SensorTimestamp":100,"extra":[1,2]},\n{"SensorTimestamp":200}]',
                      '{"SensorTimestamp":100},\n{"SensorTimestamp":200}]'):
            parser=ObjetosJSON(); frames=[]
            for caracter in texto: frames+=parser.agregar(caracter)
            self.assertEqual(frames,[100,200])

    def test_desalineacion_orden_y_campo_faltante(self):
        validar_tiempos([1000000,2000000],[0,1],1000000,0,None)
        with self.assertRaises(ValueError): validar_tiempos([1000000,2000000],[0,2],1000000,0,None)
        with self.assertRaises(ValueError): validar_tiempos([1000000],[0],1000000,0,1000000)
        with self.assertRaises(ValueError): ObjetosJSON().agregar('{"otro":1}')


class Cuota(unittest.TestCase):
    def test_borra_antiguo_no_protegido_y_sus_vinculos(self):
        with tempfile.TemporaryDirectory() as temporal:
            carpeta=Path(temporal)
            db=sqlite3.connect(':memory:'); self.addCleanup(db.close)
            esquema(db)
            for i in range(3):
                (carpeta/f'{i}.mp4').write_bytes(b'x'*100)
                (carpeta/f'{i}.json').write_text('{}')
                db.execute('INSERT INTO videos_espacio VALUES(?,?,?,?,?,?)',
                           (str(i),f'{i}.mp4','boot',i,i+1,int(i==0)))
                db.execute('INSERT INTO video_muestras VALUES(?,?)',(str(i),str(i)))
            db.execute("INSERT INTO video_muestras VALUES('otro-video','otra-muestra')")
            db.commit()
            ajustar_cuota(db,carpeta,205)
            self.assertTrue((carpeta/'0.mp4').exists())
            self.assertFalse((carpeta/'1.mp4').exists())
            self.assertTrue((carpeta/'2.mp4').exists())
            self.assertLessEqual(ocupacion(carpeta),205)
            self.assertEqual(db.execute('SELECT count(*) FROM video_muestras').fetchone()[0],3)

    def test_parciales_no_se_borran_y_reserva_cuenta(self):
        with tempfile.TemporaryDirectory() as temporal:
            carpeta=Path(temporal); (carpeta/'parcial.h264').write_bytes(b'x'*100)
            db=sqlite3.connect(':memory:'); self.addCleanup(db.close); esquema(db)
            with self.assertRaises(RuntimeError): ajustar_cuota(db,carpeta,120,30)
            self.assertTrue((carpeta/'parcial.h264').exists())


if __name__=='__main__': unittest.main()
