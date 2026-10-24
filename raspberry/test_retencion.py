import sqlite3
import unittest
from retencion import limpiar


class Retencion(unittest.TestCase):
    def test_solo_confirmadas_antiguas_sin_video(self):
        db = sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        db.executescript('''
            CREATE TABLE muestras(id INTEGER PRIMARY KEY, muestra_id TEXT, fecha_hora_pc TEXT);
            CREATE TABLE cola_sync(muestra_id TEXT,muestra_local_id INTEGER,enviada_fecha TEXT);
            CREATE TABLE video_muestras(video_id TEXT,muestra_id TEXT);
            INSERT INTO muestras VALUES(1,'vieja','2020-01-01'),(2,'pendiente','2020-01-01'),
                (3,'protegida','2020-01-01'),(4,'nueva','2999-01-01'),(5,'sin_cola','2020-01-01');
            INSERT INTO cola_sync VALUES('vieja',1,'2020-01-02'),('pendiente',2,NULL),
                ('protegida',3,'2020-01-02'),('nueva',4,'2020-01-02');
            INSERT INTO video_muestras VALUES('video','protegida');
        ''')
        self.assertEqual(limpiar(db), 1)
        self.assertEqual(db.execute('SELECT count(*) FROM muestras').fetchone()[0], 5)
        self.assertEqual(limpiar(db, aplicar=True), 1)
        self.assertEqual([r[0] for r in db.execute('SELECT id FROM muestras ORDER BY id')], [2,3,4,5])
        self.assertEqual(db.execute("SELECT count(*) FROM cola_sync WHERE muestra_id='vieja'").fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()
