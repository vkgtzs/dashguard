"""Captura segmentada con cuota local. Linux/Raspberry; probar antes de usar horas.

Metadata y PTS se drenan en hilos mientras ffmpeg procesa segmentos cerrados.
Los tiempos originales se guardan por clip; MP4 sigue a 15 fps nominales.
"""
import argparse
try:
    import fcntl
except ImportError:
    fcntl = None  # Permitir pruebas de logica en Windows; captura solo en Linux.
import json
import os
import queue
import shutil
import sqlite3
import subprocess
import threading
import time
import uuid
from contextlib import closing
from pathlib import Path
from retencion import limpiar


def esquema(db):
    db.executescript('''
        CREATE TABLE IF NOT EXISTS videos_espacio(
            id TEXT PRIMARY KEY,archivo TEXT UNIQUE NOT NULL,boot_id TEXT NOT NULL,
            inicio_ns INTEGER NOT NULL,fin_ns INTEGER NOT NULL,
            protegido INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS video_muestras(
            video_id TEXT NOT NULL,muestra_id TEXT NOT NULL,PRIMARY KEY(video_id,muestra_id));
    ''')


def ocupacion(carpeta):
    return sum(p.stat().st_size for p in carpeta.rglob('*') if p.is_file())


def ajustar_cuota(db, carpeta, limite, reserva=0):
    """Solo borra clips registrados no protegidos de esta carpeta exclusiva."""
    if reserva > limite:
        raise RuntimeError('La cuota no alcanza para la reserva de trabajo')
    while ocupacion(carpeta) + reserva > limite:
        db.execute('BEGIN IMMEDIATE')
        try:
            fila = db.execute('SELECT id,archivo FROM videos_espacio WHERE protegido=0 ORDER BY rowid LIMIT 1').fetchone()
            if fila is None:
                raise RuntimeError('Cuota ocupada por protegidos o parciales; se detiene sin borrarlos')
            identificador,nombre=fila
            ruta=carpeta/nombre
            if ruta.resolve().parent != carpeta.resolve() or ruta.is_symlink():
                raise ValueError('Ruta de video fuera de carpeta administrada')
            ruta.unlink(missing_ok=True)
            ruta.with_suffix('.json').unlink(missing_ok=True)
            db.execute('DELETE FROM video_muestras WHERE video_id=?',(identificador,))
            db.execute('DELETE FROM videos_espacio WHERE id=?',(identificador,))
            db.commit()
            print('Rotado por espacio:',nombre,flush=True)
        except BaseException:
            db.rollback()
            raise


class ObjetosJSON:
    """Acepta array JSON o objetos separados por comas del stdout de rpicam."""
    def __init__(self):
        self.buffer=''
        self.decoder=json.JSONDecoder()

    def agregar(self,texto):
        self.buffer+=texto
        resultado=[]
        while True:
            self.buffer=self.buffer.lstrip(' \r\n\t[, ]')
            if not self.buffer:
                break
            try:
                valor,fin=self.decoder.raw_decode(self.buffer)
            except json.JSONDecodeError:
                if len(self.buffer)>1024*1024:
                    raise ValueError('Metadata incompleta o inesperada supera 1 MiB')
                break
            if not isinstance(valor,dict) or type(valor.get('SensorTimestamp')) is not int:
                raise ValueError('Metadata sin SensorTimestamp entero')
            resultado.append(valor['SensorTimestamp'])
            self.buffer=self.buffer[fin:]
        return resultado


def leer_metadata(stream, salida, errores):
    parser=ObjetosJSON()
    try:
        while True:
            bloque=os.read(stream.fileno(),65536)
            if not bloque:
                break
            for sensor in parser.agregar(bloque.decode('ascii')):
                salida.put_nowait(sensor)
        if parser.buffer.strip(' \n\r\t,[]'):
            raise ValueError('Metadata truncada')
    except Exception as error:
        errores.put(str(error))


def leer_pts(fd, salida, errores):
    try:
        with os.fdopen(fd,'r',encoding='ascii') as stream:
            for linea in stream:
                if linea.strip() and not linea.startswith('#'):
                    salida.put_nowait(float(linea))
    except Exception as error:
        errores.put(str(error))


def drenar(cola,destino):
    while True:
        try: destino.append(cola.get_nowait())
        except queue.Empty: return


def validar_tiempos(sensores,pts,base_sensor,base_pts,previo):
    if len(sensores)!=len(pts) or not sensores:
        raise ValueError('Tiempos incompatibles')
    for sensor,pt in zip(sensores,pts):
        if previo is not None and sensor<=previo:
            raise ValueError('SensorTimestamp no creciente')
        if abs((sensor-base_sensor)/1e6-(pt-base_pts))>0.1:
            raise ValueError('Secuencia PTS y SensorTimestamp desalineada')
        previo=sensor
    if any(b<=a for a,b in zip(pts,pts[1:])):
        raise ValueError('PTS no creciente')


def contar_frames(bruto):
    r=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-count_frames',
        '-show_entries','stream=nb_read_frames','-of','json',str(bruto)],
        capture_output=True,text=True,check=True,timeout=60)
    if r.stderr.strip():
        raise ValueError('Error al decodificar segmento: '+r.stderr)
    n=int(json.loads(r.stdout)['streams'][0]['nb_read_frames'])
    if n<=0: raise ValueError('Segmento sin frames')
    return n


def guardar_clip(db,carpeta,bruto,sensores,pts,fin,boot):
    identificador=str(uuid.uuid4())
    final=carpeta/(identificador+'.mp4')
    temporal=carpeta/(identificador+'.part.mp4')
    subprocess.run(['ffmpeg','-v','error','-n','-fflags','+genpts','-r','15',
        '-i',str(bruto),'-c:v','copy','-movflags','+faststart',str(temporal)],
        check=True,timeout=60)
    muestras=db.execute('''SELECT muestra_id,fecha_hora_pc,boottime_ns,datos_json
        FROM muestras WHERE boot_id=? AND boottime_ns>=? AND boottime_ns<?
        ORDER BY boottime_ns''',(boot,sensores[0],fin)).fetchall()
    datos=dict(video_id=identificador,archivo=final.name,boot_id=boot,
        inicio_ns=sensores[0],fin_exclusivo_ns=fin,
        sensor_timestamps_ns=sensores,pts_originales_ms=pts,
        asociacion='SensorTimestamp y marca host IMU CLOCK_BOOTTIME; GPS ultimo fix reciente',
        advertencia='MP4 15 fps nominales; ver PTS originales para cadencia real',
        muestras=[dict(muestra_id=m[0],fecha_hora=m[1],boottime_ns=m[2],datos=json.loads(m[3])) for m in muestras])
    sidecar=final.with_suffix('.json')
    temporal.rename(final)
    sidecar.write_text(json.dumps(datos,ensure_ascii=False),encoding='utf-8')
    with db:
        db.execute('''INSERT INTO videos_espacio(id,archivo,boot_id,inicio_ns,fin_ns)
            VALUES(?,?,?,?,?)''',(identificador,final.name,boot,sensores[0],fin))
        db.executemany('INSERT INTO video_muestras VALUES(?,?)',[(identificador,m[0]) for m in muestras if m[0]])
    bruto.unlink()
    print(f'Cerrado {final.name}: {len(sensores)} frames, {len(muestras)} muestras, '+
          f'{sum(json.loads(m[3]).get("gps_valido") is True for m in muestras)} GPS validas',flush=True)


def ejecutar(db,carpeta,duracion,segmento,limite):
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    cols={c[1] for c in db.execute('PRAGMA table_info(muestras)')}
    if not {'boottime_ns','boot_id','muestra_id'}<=cols:
        raise RuntimeError('Falta registrador con boottime_ns')
    ultima=db.execute('SELECT max(boottime_ns) FROM muestras WHERE boot_id=?',(boot,)).fetchone()[0]
    if ultima is None or not 0<=time.clock_gettime_ns(time.CLOCK_BOOTTIME)-ultima<5e9:
        raise RuntimeError('Inicia captura de sensores y espera calibracion')
    esquema(db)
    # Reserva conservadora: dos brutos y una conversion, mas metadata.
    reserva=int(3*segmento*2_000_000/8*1.5)+2*1024**2
    ajustar_cuota(db,carpeta,limite,reserva)
    sesion=carpeta/('sesion_'+str(uuid.uuid4()))
    sesion.mkdir()
    q_sensor=queue.Queue(maxsize=10000)
    q_pts=queue.Queue(maxsize=10000)
    errores=queue.Queue()
    fd_lectura,fd_escritura=os.pipe()
    comando=['rpicam-vid','--nopreview','--timeout',str(duracion*1000),
        '--width','1280','--height','720','--framerate','15','--codec','h264',
        '--bitrate','2000000','--inline','--intra','15','--segment',str(segmento*1000),
        '--flush','--metadata','-','--metadata-format','json',
        '--save-pts',f'/proc/self/fd/{fd_escritura}',
        '--output',str(sesion/'parte_%08d.h264')]
    try:
        proceso=subprocess.Popen(comando,stdout=subprocess.PIPE,pass_fds=(fd_escritura,))
    except BaseException:
        os.close(fd_lectura)
        raise
    finally:
        os.close(fd_escritura)
    hilos=[threading.Thread(target=leer_metadata,args=(proceso.stdout,q_sensor,errores),daemon=True),
           threading.Thread(target=leer_pts,args=(fd_lectura,q_pts,errores),daemon=True)]
    for hilo in hilos: hilo.start()
    sensores=[]; pts=[]; vistos=set(); hechos=set(); conteos={}
    base_sensor=None; base_pts=None; previo=None
    inicio=time.monotonic(); sin_progreso=inicio; ultima_limpieza=inicio
    try:
        while True:
            terminado=proceso.poll() is not None
            if terminado:
                for hilo in hilos: hilo.join(timeout=5)
                if any(h.is_alive() for h in hilos): raise RuntimeError('Lectores no terminaron')
                if proceso.returncode: raise RuntimeError(f'rpicam fallo: {proceso.returncode}')
            if not errores.empty(): raise RuntimeError('Tiempos: '+errores.get())
            drenar(q_sensor,sensores); drenar(q_pts,pts)
            if len(sensores)>10000 or len(pts)>10000:
                raise RuntimeError('Procesamiento atrasado; detener para no agotar RAM')
            if base_sensor is None and sensores and pts:
                base_sensor=sensores[0]; base_pts=pts[0]
            vistos.update(sesion.glob('parte_*.h264'))
            orden=sorted(vistos)
            for i,bruto in enumerate(orden):
                if bruto in hechos: continue
                if i+1==len(orden) and not terminado: break
                if not bruto.stat().st_size:
                    if terminado:
                        bruto.unlink(); hechos.add(bruto); continue
                    break
                n=conteos.setdefault(bruto,0)
                if not n:
                    n=contar_frames(bruto); conteos[bruto]=n
                necesarios=n if terminado and i+1==len(orden) else n+1
                drenar(q_sensor,sensores); drenar(q_pts,pts)
                if len(sensores)<necesarios or len(pts)<n:
                    if terminado: raise ValueError('Frames sin metadata/PTS suficientes')
                    break
                validar_tiempos(sensores[:n],pts[:n],base_sensor,base_pts,previo)
                fin=sensores[n] if len(sensores)>n else sensores[n-1]+1
                # Espacio para MP4 mientras aun existe el bruto y crece el activo.
                ajustar_cuota(db,carpeta,limite,int(bruto.stat().st_size*1.5)+2*1024**2)
                guardar_clip(db,carpeta,bruto,sensores[:n],pts[:n],fin,boot)
                previo=sensores[n-1]
                del sensores[:n]; del pts[:n]
                hechos.add(bruto); sin_progreso=time.monotonic()
                ajustar_cuota(db,carpeta,limite,reserva if not terminado else 0)
                print(f'Ocupacion administrada: {ocupacion(carpeta)/1024**2:.1f} MiB / {limite/1024**2:.1f} MiB',flush=True)
            if terminado:
                if sensores or pts: raise ValueError('Metadata/PTS sobrantes; revisar correspondencia')
                break
            if time.monotonic()-sin_progreso>max(60,segmento*3):
                raise RuntimeError('Sin segmentos verificables; se conservan parciales')
            # Cuota blanda: se comprueba periodicamente, reserva permite fluctuacion.
            ajustar_cuota(db,carpeta,limite)
            if shutil.disk_usage(carpeta).free<256*1024**2:
                raise RuntimeError('Reserva del sistema agotada')
            if time.monotonic()-ultima_limpieza>60:
                limpiar(db,aplicar=True); ultima_limpieza=time.monotonic()
            time.sleep(0.2)
        limpiar(db,aplicar=True)
        if sesion.exists() and not any(sesion.iterdir()): sesion.rmdir()
        print('Grabacion terminada. Sensores siguen activos hasta detener su servicio.',flush=True)
    finally:
        if proceso.poll() is None:
            proceso.terminate()
            try: proceso.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proceso.kill(); proceso.wait()
        for hilo in hilos: hilo.join(timeout=5)
        drenar(q_sensor,sensores); drenar(q_pts,pts)
        if sensores or pts or any(sesion.glob('*.h264')):
            sesion.mkdir(exist_ok=True)
            (sesion/'tiempos_pendientes.json').write_text(json.dumps(dict(
                sensor_timestamps_ns=sensores,pts_ms=pts,boot_id=boot,
                base_sensor=base_sensor,base_pts=base_pts,
                advertencia='Recuperacion manual; ultimo JSON de metadata puede quedar truncado')),
                encoding='utf-8')
        proceso.stdout.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--duracion',type=int,default=180,help='Segundos; 0 hasta Ctrl+C')
    p.add_argument('--segmento',type=int,default=10)
    p.add_argument('--limite-mib',type=int,default=30)
    a=p.parse_args()
    if fcntl is None: p.error('La grabacion requiere Linux/Raspberry')
    if a.duracion<0 or not 5<=a.segmento<=300 or a.limite_mib<20:
        p.error('Duracion >=0, segmento 5..300 s, limite >=20 MiB')
    carpeta=Path.home()/'dashguard/videos/loop_espacio'
    carpeta.mkdir(parents=True,exist_ok=True)
    with (carpeta/'.grabacion.lock').open('w') as bloqueo:
        try: fcntl.flock(bloqueo,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise RuntimeError('Ya hay una grabacion de este programa')
        ruta=Path.home()/'dashguard/datos/dashguard.sqlite3'
        with closing(sqlite3.connect(f'{ruta.as_uri()}?mode=rw',uri=True,timeout=10)) as db:
            ejecutar(db,carpeta,a.duracion,a.segmento,a.limite_mib*1024**2)


if __name__=='__main__':
    try: main()
    except KeyboardInterrupt: print('Detenido; ultimo bruto/tiempos en RAM pueden quedar sin procesar. No se borran parciales.')
