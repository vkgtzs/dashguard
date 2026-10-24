"""Prueba finita de 90 s. Valida y vincula segmentos por SensorTimestamp.

Procesa al terminar la captura; no es aun loop indefinido ni preserva PTS
variables dentro del MP4. Los originales de tiempos quedan en cada sesion.
"""
import json
import shutil
import sqlite3
import subprocess
import time
import uuid
from contextlib import closing
from pathlib import Path
from retencion import limpiar


def ventanas(metadata, pts, conteos):
    sensores = [m.get('SensorTimestamp') for m in metadata]
    if (not sensores or any(type(s) is not int for s in sensores)
            or len(sensores) != len(pts) or sum(conteos) != len(sensores)
            or any(n <= 0 for n in conteos)):
        raise ValueError('Conteos de frames, metadata y PTS incompatibles')
    if any(b <= a for a,b in zip(sensores,sensores[1:])) or any(b <= a for a,b in zip(pts,pts[1:])):
        raise ValueError('Timestamps no crecientes')
    # Verificar toda la secuencia relativa, no solo los conteos.
    for sensor, pt in zip(sensores,pts):
        if abs((sensor-sensores[0])/1e6 - (pt-pts[0])) > 0.1:
            raise ValueError('PTS y SensorTimestamp no se alinean (tolerancia 0.1 ms)')
    resultado=[]
    offset=0
    for n in conteos:
        fin=offset+n
        resultado.append(dict(primer_indice=offset,fin_indice=fin,
            inicio_ns=sensores[offset],ultimo_frame_ns=sensores[fin-1],
            fin_exclusivo_ns=sensores[fin] if fin<len(sensores) else sensores[-1]+1))
        offset=fin
    return resultado


def esquema(db):
    db.executescript('''
        CREATE TABLE IF NOT EXISTS videos_timestamps(
            id TEXT PRIMARY KEY, archivo TEXT UNIQUE NOT NULL, sesion TEXT NOT NULL,
            boot_id TEXT NOT NULL,inicio_ns INTEGER NOT NULL,fin_ns INTEGER NOT NULL,
            protegido INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS video_muestras(
            video_id TEXT NOT NULL,muestra_id TEXT NOT NULL,PRIMARY KEY(video_id,muestra_id));
    ''')


def rotar(db,carpeta):
    filas=db.execute('SELECT id,archivo FROM videos_timestamps WHERE protegido=0 ORDER BY rowid DESC').fetchall()
    for identificador,nombre in filas[6:]:
        ruta=carpeta/nombre
        if ruta.resolve().parent!=carpeta.resolve():
            raise ValueError('Ruta fuera de carpeta')
        ruta.unlink(missing_ok=True)
        ruta.with_suffix('.json').unlink(missing_ok=True)
        with db:
            db.execute('DELETE FROM video_muestras WHERE video_id=?',(identificador,))
            db.execute('DELETE FROM videos_timestamps WHERE id=?',(identificador,))
        print('Rotado:',nombre,flush=True)


def main():
    carpeta=Path.home()/'dashguard/videos/timestamps_prueba'
    sesion=carpeta/('sesion_'+str(uuid.uuid4()))
    sesion.mkdir(parents=True)
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    ruta=Path.home()/'dashguard/datos/dashguard.sqlite3'
    with closing(sqlite3.connect(f'{ruta.as_uri()}?mode=rw',uri=True,timeout=10)) as db:
        cols={c[1] for c in db.execute('PRAGMA table_info(muestras)')}
        if not {'boottime_ns','boot_id','muestra_id'}<=cols:
            raise RuntimeError('Instalar e iniciar registrador actualizado primero')
        ultima=db.execute('SELECT max(boottime_ns) FROM muestras WHERE boot_id=?',(boot,)).fetchone()[0]
        if ultima is None or not 0<=time.clock_gettime_ns(time.CLOCK_BOOTTIME)-ultima<5_000_000_000:
            raise RuntimeError('No hay muestras recientes del arranque actual')
        esquema(db)
        if shutil.disk_usage(carpeta).free<512*1024**2:
            raise RuntimeError('Se requieren al menos 512 MiB libres')
        comando=['rpicam-vid','--nopreview','--timeout','90000','--width','1280',
            '--height','720','--framerate','15','--codec','h264','--bitrate','2000000',
            '--inline','--intra','15','--segment','10000','--save-pts',str(sesion/'frames.pts'),
            '--metadata',str(sesion/'metadata.json'),'--metadata-format','json',
            '--output',str(sesion/'parte_%04d.h264')]
        with subprocess.Popen(comando) as proceso:
            try:
                while proceso.poll() is None:
                    if shutil.disk_usage(carpeta).free<256*1024**2:
                        raise RuntimeError('Reserva de espacio agotada')
                    time.sleep(0.2)
                if proceso.returncode:
                    raise RuntimeError('Fallo rpicam; se conservan originales')
            finally:
                if proceso.poll() is None:
                    proceso.terminate()
                    try: proceso.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        proceso.kill()
                        proceso.wait()
        brutos=sorted(sesion.glob('parte_*.h264'))
        brutos=[p for p in brutos if p.stat().st_size]
        metadata=json.loads((sesion/'metadata.json').read_text())
        pts=[float(l) for l in (sesion/'frames.pts').read_text().splitlines() if l.strip() and not l.startswith('#')]
        conteos=[]
        for bruto in brutos:
            resultado=subprocess.run(['ffprobe','-v','error','-select_streams','v:0',
                '-count_frames','-show_entries','stream=nb_read_frames','-of','json',str(bruto)],
                check=True,capture_output=True,text=True,timeout=60)
            if resultado.stderr.strip():
                raise RuntimeError('Error de decodificacion ffprobe: '+resultado.stderr)
            conteos.append(int(json.loads(resultado.stdout)['streams'][0]['nb_read_frames']))
        limites=ventanas(metadata,pts,conteos)
        print('Validado:',sum(conteos),'fotogramas en',len(brutos),'segmentos',flush=True)
        for bruto,limite in zip(brutos,limites):
            identificador=str(uuid.uuid4())
            salida=carpeta/(identificador+'.mp4')
            temporal=carpeta/(identificador+'.part.mp4')
            subprocess.run(['ffmpeg','-v','error','-n','-fflags','+genpts','-r','15',
                '-i',str(bruto),'-c:v','copy','-movflags','+faststart',str(temporal)],check=True,timeout=60)
            temporal.rename(salida)
            filas=db.execute('''SELECT muestra_id,fecha_hora_pc,boottime_ns,datos_json
                FROM muestras WHERE boot_id=? AND boottime_ns>=? AND boottime_ns<?
                ORDER BY boottime_ns''',(boot,limite['inicio_ns'],limite['fin_exclusivo_ns'])).fetchall()
            muestras=[dict(muestra_id=f[0],fecha_hora=f[1],boottime_ns=f[2],datos=json.loads(f[3])) for f in filas]
            inicio=limite['primer_indice']; fin=limite['fin_indice']
            datos=dict(video_id=identificador,archivo=salida.name,boot_id=boot,
                sesion=sesion.name,**limite,sensor_timestamps_ns=[m['SensorTimestamp'] for m in metadata[inicio:fin]],
                pts_originales_ms=pts[inicio:fin],muestras=muestras,
                asociacion='SensorTimestamp CLOCK_BOOTTIME; IMU marcada por host antes de I2C',
                advertencia='GPS es ultimo fix reciente, no tiempo de adquisicion; MP4 usa 15fps nominales')
            salida.with_suffix('.json').write_text(json.dumps(datos,ensure_ascii=False),encoding='utf-8')
            with db:
                db.execute('''INSERT INTO videos_timestamps
                    (id,archivo,sesion,boot_id,inicio_ns,fin_ns) VALUES(?,?,?,?,?,?)''',
                    (identificador,salida.name,sesion.name,boot,limite['inicio_ns'],limite['fin_exclusivo_ns']))
                db.executemany('INSERT INTO video_muestras VALUES(?,?)',[(identificador,f[0]) for f in filas if f[0]])
            bruto.unlink()
            print(f'Cerrado {salida.name}: {len(muestras)} muestras, '+
                f'{sum(m["datos"].get("gps_valido") is True for m in muestras)} GPS validas',flush=True)
            rotar(db,carpeta)
            limpiar(db,aplicar=True)
        print('Terminado. Originales de tiempos conservados en',sesion)


if __name__=='__main__':
    try: main()
    except KeyboardInterrupt: print('Interrumpido: se conservan parciales para revision')
