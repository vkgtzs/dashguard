import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from video_continuo import esquema, rotar


class Rotacion(unittest.TestCase):
    def test_conserva_seis_y_protegido_sin_tocar_otra_tabla(self):
        with TemporaryDirectory() as temp:
            carpeta=Path(temp)
            db=sqlite3.connect(':memory:')
            self.addCleanup(db.close)
            esquema(db)
            for i in range(9):
                nombre=f'{i}.mp4'
                (carpeta/nombre).write_bytes(b'video')
                (carpeta/f'{i}.json').write_text('{}')
                db.execute('INSERT INTO videos_continuos VALUES(?,?,?,?,?,?)',
                           (str(i),nombre,i,i+1,'boot',int(i==0)))
                db.execute('INSERT INTO video_muestras VALUES(?,?)',(str(i),str(i)))
            db.execute("INSERT INTO video_muestras VALUES('otro-loop','muestra-ajena')")
            db.commit()
            rotar(db,carpeta)
            self.assertTrue((carpeta/'0.mp4').exists())
            self.assertFalse((carpeta/'1.mp4').exists())
            self.assertFalse((carpeta/'2.json').exists())
            self.assertEqual(len(list(carpeta.glob('*.mp4'))),7)
            self.assertEqual(db.execute('SELECT count(*) FROM video_muestras').fetchone()[0],8)


if __name__=='__main__':
    unittest.main()
