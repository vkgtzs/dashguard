import io
import json
import sqlite3
import tempfile
import unittest
import uuid
from contextlib import closing
from pathlib import Path
from urllib.error import URLError

from sincronizar import abrir, preparar, encolar, sincronizar


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ruta = Path(self.tmp.name) / 'datos.sqlite3'
        db = sqlite3.connect(self.ruta)
        db.execute('CREATE TABLE muestras (id INTEGER PRIMARY KEY, fecha_hora_pc TEXT, datos_json TEXT)')
        self.datos = dict(magnitud_ms2=9.81, ax_ms2=0, ay_ms2=0, az_ms2=9.81,
                          gx_grados_s=0, gy_grados_s=0, gz_grados_s=0, gps_valido=False)
        db.execute('INSERT INTO muestras (fecha_hora_pc, datos_json) VALUES (?, ?)',
                   ('2026-10-21T18:29:45Z', json.dumps(self.datos)))
        db.commit()
        db.close()
        self.db = abrir(self.ruta)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def preparar(self):
        preparar(self.db)
        encolar(self.db, 'dashguard-pi-001')

    def respuesta(self, request, timeout):
        payload = json.loads(request.data)
        respuesta = io.BytesIO(json.dumps({'medicion': {**payload, 'id': 131}}).encode())
        respuesta.status = 201
        return respuesta

    def test_migracion_respaldo_uuid_nuevas_y_contenido_estable(self):
        self.preparar()
        fila = dict(self.db.execute('SELECT * FROM cola_sync').fetchone())
        self.assertEqual(uuid.UUID(fila['muestra_id']).version, 4)
        with closing(sqlite3.connect(self.ruta.with_name('antes_sincronizacion.sqlite3'))) as copia:
            self.assertEqual(copia.execute('SELECT count(*) FROM muestras').fetchone()[0], 1)
        self.db.execute('INSERT INTO muestras (fecha_hora_pc, datos_json) VALUES (?, ?)',
                        ('2026-10-21T18:29:46Z', json.dumps(self.datos)))
        self.db.commit()
        nueva = self.db.execute('SELECT muestra_id FROM muestras WHERE id=2').fetchone()[0]
        self.assertEqual(uuid.UUID(nueva).version, 4)
        preparar(self.db)
        encolar(self.db, 'otro-dispositivo')
        self.assertEqual(dict(self.db.execute('SELECT * FROM cola_sync WHERE muestra_local_id=1').fetchone()), fila)

    def test_sin_red_conserva_pendiente_y_reintenta_mismo_payload(self):
        self.preparar()
        originales = self.db.execute('SELECT muestra_id, payload FROM cola_sync').fetchone()
        def falla(request, timeout):
            raise URLError('sin conexion')
        self.assertFalse(sincronizar(self.db, 'http://pc:3000/mediciones', enviar=falla))
        self.assertIsNone(self.db.execute('SELECT enviada_fecha FROM cola_sync').fetchone()[0])
        self.assertTrue(sincronizar(self.db, 'http://pc:3000/mediciones', enviar=self.respuesta))
        self.assertEqual(tuple(self.db.execute('SELECT muestra_id, payload FROM cola_sync').fetchone()), tuple(originales))
        self.assertIsNotNone(self.db.execute('SELECT enviada_fecha FROM cola_sync').fetchone()[0])
        def no_debe_enviar(request, timeout):
            self.fail('Una muestra confirmada no debe reenviarse')
        sincronizar(self.db, 'http://pc:3000/mediciones', enviar=no_debe_enviar)

    def test_confirmacion_incorrecta_no_marca_enviada(self):
        self.preparar()
        def incorrecta(request, timeout):
            respuesta = io.BytesIO(b'{"medicion":{"id":12,"muestra_id":"otro"}}')
            respuesta.status = 200
            return respuesta
        self.assertFalse(sincronizar(self.db, 'http://pc:3000/mediciones', enviar=incorrecta))
        self.assertIsNone(self.db.execute('SELECT enviada_fecha FROM cola_sync').fetchone()[0])

    def test_fallo_imu_permanece_local_sin_bloquear_sanas(self):
        datos={**self.datos,'imu_valida':False,'magnitud_ms2':None,'gps_valido':True}
        self.db.execute('UPDATE muestras SET datos_json=? WHERE id=1',(json.dumps(datos),))
        self.db.execute('INSERT INTO muestras (fecha_hora_pc, datos_json) VALUES (?,?)',
                        ('2026-10-21T18:30:00Z',json.dumps(self.datos)))
        self.db.commit()
        self.preparar()
        self.assertEqual(self.db.execute('SELECT count(*) FROM muestras').fetchone()[0],2)
        self.assertEqual(self.db.execute('SELECT muestra_local_id FROM cola_sync').fetchone()[0],2)


if __name__ == '__main__':
    unittest.main()
