import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from urllib.error import URLError
from dashcam_estado import abrir,encolar,sha_archivo,recuperar
from dashcam_sync import una_vez
from dashcam_verificar import verificar


class Respuesta:
    status=200
    def __init__(self,datos):self.datos=json.dumps(datos).encode()
    def __enter__(self):return self
    def __exit__(self,*_):pass
    def read(self):return self.datos


class Offline(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.db=abrir(Path(self.temp.name)/'estado.sqlite3');self.addCleanup(self.db.close)
        self.config=dict(backend='https://unidad.invalid',device_id='unidad',device_token='x'*40)
        self.trip=str(uuid.uuid4());self.id=str(uuid.uuid4())
        encolar(self.db,self.id,self.trip,'muestra',dict(imu_valida=False,gps_valido=False,valor=None));self.db.commit()

    def test_video_grande_confirma_todas_partes_y_reintenta_sin_borrar(self):
        from dashcam_estado import partes_archivo
        ruta=Path(self.temp.name)/'grande.mp4';ruta.write_bytes(b'x'*(9*1024**2))
        v=str(uuid.uuid4());sha=sha_archivo(ruta)
        partes=partes_archivo(ruta,'unidad',self.trip,v)
        self.db.execute('INSERT INTO dashcam_archivos VALUES(?,?,?,?,?,NULL)',(v,self.trip,str(ruta),sha,ruta.stat().st_size))
        encolar(self.db,v,self.trip,'video',dict(partes=partes));self.db.commit()
        llamadas=[]
        def responder(req,**_):
            if req.method=='PUT':
                n=int(req.full_url.rsplit('/',1)[1]);llamadas.append(n)
                return Respuesta(dict(bloque_id=v,numero=n,recorrido_id=self.trip,device_id='unidad',
                    sha256=hashlib.sha256(req.data).hexdigest(),bytes=len(req.data)))
            return Respuesta(dict(confirmados=[dict(id=r['id'],sha256=r['sha256'],device_id='unidad') for r in json.loads(req.data)['registros']]))
        def cortar(req,**kw):
            if req.full_url.endswith('/1'):raise URLError('corte simulado')
            return responder(req,**kw)
        with self.assertRaises(URLError):una_vez(self.db,self.config,cortar)
        self.assertIsNone(self.db.execute('SELECT confirmado FROM dashcam_archivos').fetchone()[0])
        una_vez(self.db,self.config,responder)
        self.assertEqual(llamadas,[0,0,1]);self.assertTrue(ruta.exists())
        self.assertIsNotNone(self.db.execute('SELECT confirmado FROM dashcam_archivos').fetchone()[0])

    def test_sin_red_conserva_contenido_uuid_y_reintento(self):
        original=dict(self.db.execute('SELECT * FROM dashcam_outbox').fetchone())
        def fallo(*a,**k):raise URLError('offline simulado')
        with self.assertRaises(URLError):una_vez(self.db,self.config,fallo)
        self.assertEqual(dict(self.db.execute('SELECT * FROM dashcam_outbox').fetchone()),original)
        cuerpos=[]
        def bien(req,**_):
            r=json.loads(req.data)['registros'];cuerpos.append(req.data)
            return Respuesta(dict(confirmados=[dict(id=x['id'],sha256=x['sha256'],device_id='unidad') for x in r]))
        self.assertEqual(una_vez(self.db,self.config,bien),1)
        self.assertEqual(una_vez(self.db,self.config,bien),0)
        self.assertEqual(len(cuerpos),1)

    def test_confirmacion_incorrecta_no_marca_enviado(self):
        def incompleta(*a,**k):return Respuesta(dict(confirmados=[dict(id=self.id,sha256='0'*64,device_id='unidad')]))
        with self.assertRaises(ValueError):una_vez(self.db,self.config,incompleta)
        self.assertIsNone(self.db.execute('SELECT confirmado FROM dashcam_outbox').fetchone()[0])

    def test_no_sobrescribe_uuid_local(self):
        with self.assertRaises(ValueError):encolar(self.db,self.id,self.trip,'muestra',dict(otro=True))
        datos=dict(imu_valida=False,gps_valido=False,valor=None)
        with self.assertRaises(ValueError):encolar(self.db,self.id,str(uuid.uuid4()),'muestra',datos)

    def test_recupera_cierre_estimado_sin_inventar_hora_ni_borrar_brutos(self):
        carpeta=Path(self.temp.name)/'recorrido';carpeta.mkdir()
        bruto=carpeta/'pendiente.h264';bruto.write_bytes(b'parcial sintetico')
        self.db.executescript('''CREATE TABLE muestras(id INTEGER PRIMARY KEY,muestra_id TEXT,fecha_hora_pc TEXT,
          datos_json TEXT,boot_id TEXT,boottime_ns INTEGER);
          CREATE TABLE videos_espacio(id TEXT,archivo TEXT,boot_id TEXT,inicio_ns INTEGER);''')
        self.db.execute('INSERT INTO dashcam_recorridos VALUES(?,?,?,?,?,?,?,?)',
            (self.trip,'boot-anterior',100,500,None,'activo',str(carpeta),str(uuid.uuid4())))
        for t in (150,750):self.db.execute('INSERT INTO muestras(muestra_id,fecha_hora_pc,datos_json,boot_id,boottime_ns) VALUES(?,?,?,?,?)',
           (str(uuid.uuid4()),'2026-01-01T00:00:00Z','{}','boot-anterior',t))
        self.db.commit();recuperar(self.db)
        r=self.db.execute('SELECT estado,fin_ns FROM dashcam_recorridos').fetchone()
        self.assertEqual(tuple(r),('interrumpido',500));self.assertTrue(bruto.exists())
        self.assertEqual(self.db.execute("SELECT count(*) FROM dashcam_outbox WHERE tipo='muestra'").fetchone()[0],2)
        fin=json.loads(self.db.execute("SELECT contenido_json FROM dashcam_outbox WHERE tipo='fin'").fetchone()[0])
        self.assertTrue(fin['cierre_estimado']);self.assertEqual(fin['boot_id'],'boot-anterior')

    def test_video_reintento_valida_bytes_y_nunca_borra_local(self):
        ruta=Path(self.temp.name)/'clip.mp4';ruta.write_bytes(b'video sintetico')
        v=str(uuid.uuid4());sha=sha_archivo(ruta)
        self.db.execute('INSERT INTO dashcam_archivos VALUES(?,?,?,?,?,NULL)',(v,self.trip,str(ruta),sha,ruta.stat().st_size));self.db.commit()
        def respuesta(req,**_):
            if req.method=='PUT':return Respuesta(dict(video_id=v,recorrido_id=self.trip,sha256=sha,bytes=ruta.stat().st_size,device_id='unidad'))
            return Respuesta(dict(confirmados=[dict(id=self.id,sha256=hashlib.sha256(json.loads(req.data)['registros'][0]['contenido_json'].encode()).hexdigest(),device_id='unidad')]))
        una_vez(self.db,self.config,respuesta)
        self.assertTrue(ruta.exists());self.assertIsNotNone(self.db.execute('SELECT confirmado FROM dashcam_archivos').fetchone()[0])

    def test_informe_advierte_hueco_entre_clips_y_corrupcion_sin_borrar(self):
        from video_espacio import esquema
        esquema(self.db)
        trip=str(uuid.uuid4());carpeta=Path(self.temp.name)/'videos';carpeta.mkdir()
        self.db.execute('INSERT INTO dashcam_recorridos VALUES(?,?,?,?,?,?,?,?)',
          (trip,'boot-prueba',0,600000000,600000000,'completo',str(carpeta),str(uuid.uuid4())))
        rutas=[]
        for n,inicio in enumerate((0,400000000)):
            id=str(uuid.uuid4());ruta=carpeta/(id+'.mp4');ruta.write_bytes(b'video sintetico');rutas.append(ruta)
            meta=dict(boot_id='boot-prueba',sensor_timestamps_ns=[inicio,inicio+66666667,inicio+133333334],
                      pts_originales_ms=[0,66.666667,133.333334],fin_exclusivo_ns=inicio+200000000)
            ruta.with_suffix('.json').write_text(json.dumps(meta))
            self.db.execute('INSERT INTO dashcam_archivos VALUES(?,?,?,?,?,NULL)',(id,trip,str(ruta),sha_archivo(ruta),ruta.stat().st_size))
            self.db.execute('INSERT INTO videos_espacio VALUES(?,?,?,?,?,?)',(id,ruta.name,'boot-prueba',inicio,inicio+200000000,1))
        self.db.commit()
        informe=verificar(self.db,trip)
        self.assertEqual(informe['frames_catalogados'],6)
        self.assertEqual(informe['huecos_mayores_100ms'],1)
        self.assertEqual(informe['fronteras_discontinuas'],1)
        self.assertEqual(informe['errores_integridad'],[])
        rutas[0].write_bytes(b'corrupcion sintetica')
        self.assertEqual(len(verificar(self.db,trip)['errores_integridad']),1)
        self.assertTrue(rutas[0].exists())


if __name__=='__main__':unittest.main()
