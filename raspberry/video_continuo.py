"""Prueba de 90 s: una captura rpicam, segmentos, telemetria aproximada y rotacion.

Las ventanas usan deteccion de archivos, no timestamps de fotogramas. El margen
es heuristico y no garantiza precision temporal. Se conserva el bruto ante fallo.
"""
import json
import shutil
import sqlite3
import subprocess
import time
import uuid
from contextlib import closing
from datetime import datetime, timezone, timedelta
from pathlib import Path
from retencion import limpiar


def esquema(db):
    db.executescript('''
        CREATE TABLE IF NOT EXISTS videos_continuos (
            id TEXT PRIMARY KEY, archivo TEXT NOT NULL UNIQUE,
            inicio_mono REAL NOT NULL, fin_mono REAL NOT NULL,
            boot_id TEXT NOT NULL, protegido INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS video_muestras (
            video_id TEXT NOT NULL, muestra_id TEXT NOT NULL,
            PRIMARY KEY(video_id,muestra_id)
        );
    ''')


def rotar(db, carpeta, conservar=6):
    filas = db.execute('SELECT id,archivo FROM videos_continuos WHERE protegido=0 ORDER BY rowid DESC').fetchall()
    for identificador, nombre in filas[conservar:]:
        ruta = carpeta / nombre
        if ruta.resolve().parent != carpeta.resolve():
            raise ValueError('Ruta fuera de carpeta de prueba')
        ruta.unlink(missing_ok=True)
        ruta.with_suffix('.json').unlink(missing_ok=True)
        with db:
            db.execute('DELETE FROM video_muestras WHERE video_id=?', (identificador,))
            db.execute('DELETE FROM videos_continuos WHERE id=?', (identificador,))
        print('Rotado:', nombre, flush=True)


def finalizar(db, carpeta, bruto, inicio, fin, boot, origen_mono, origen_utc):
    identificador = str(uuid.uuid4())
    salida = carpeta / (identificador + '.mp4')
    temporal = carpeta / (identificador + '.part.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-n', '-fflags', '+genpts', '-r', '15',
        '-i', str(bruto), '-c:v', 'copy', '-movflags', '+faststart', str(temporal)],
        check=True, timeout=30)
    temporal.rename(salida)
    # Margen de 1 s para variaciones de observacion/escritura; puede solapar clips.
    filas = db.execute('''SELECT muestra_id,fecha_hora_pc,monotonic_s,datos_json
        FROM muestras WHERE boot_id=? AND monotonic_s>=? AND monotonic_s<=?
        ORDER BY monotonic_s''', (boot, inicio - 1, fin + 1)).fetchall()
    muestras = [dict(muestra_id=f[0],fecha_hora=f[1],monotonic_s=f[2],datos=json.loads(f[3])) for f in filas]
    metadata = dict(video_id=identificador,archivo=salida.name,boot_id=boot,
        inicio_mono=inicio,fin_mono=fin,margen_s=1,
        inicio_utc_estimado=(origen_utc + timedelta(seconds=inicio-origen_mono)).isoformat(),
        tipo_asociacion='aproximada por observacion de archivos; no por fotograma',
        muestras=muestras)
    salida.with_suffix('.json').write_text(json.dumps(metadata,ensure_ascii=False),encoding='utf-8')
    with db:
        db.execute('INSERT INTO videos_continuos (id,archivo,inicio_mono,fin_mono,boot_id) VALUES(?,?,?,?,?)',
                   (identificador,salida.name,inicio,fin,boot))
        db.executemany('INSERT INTO video_muestras VALUES(?,?)', [(identificador,f[0]) for f in filas if f[0]])
    bruto.unlink()
    validas = sum(m['datos'].get('gps_valido') is True for m in muestras)
    print(f'Cerrado {salida.name}: {len(muestras)} muestras, {validas} con GPS valido',flush=True)
    rotar(db,carpeta)
    print('Mediciones antiguas eliminadas:',limpiar(db,aplicar=True),flush=True)


def main():
    carpeta = Path.home() / 'dashguard/videos/continuo_prueba'
    carpeta.mkdir(parents=True,exist_ok=True)
    sesion = carpeta / ('captura_' + str(uuid.uuid4()))
    sesion.mkdir()
    ruta = Path.home() / 'dashguard/datos/dashguard.sqlite3'
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    with closing(sqlite3.connect(f'{ruta.as_uri()}?mode=rw',uri=True,timeout=10)) as db:
        columnas = {c[1] for c in db.execute('PRAGMA table_info(muestras)')}
        if not {'boot_id','muestra_id','monotonic_s'} <= columnas:
            raise RuntimeError('Falta el registrador actualizado')
        ultima = db.execute('SELECT max(monotonic_s) FROM muestras WHERE boot_id=?',(boot,)).fetchone()[0]
        if ultima is None or time.monotonic()-ultima > 5:
            raise RuntimeError('No hay mediciones recientes; iniciar servicio de captura primero')
        esquema(db)
        if shutil.disk_usage(carpeta).free < 512*1024**2:
            raise RuntimeError('Menos de 512 MiB libres')
        origen = time.monotonic()
        utc = datetime.now(timezone.utc)
        comando = ['rpicam-vid','--nopreview','--timeout','90000','--width','1280',
            '--height','720','--framerate','15','--codec','h264','--bitrate','2000000',
            '--inline','--intra','15','--segment','10000','--output',str(sesion/'parte_%04d.h264')]
        vistos = {}
        hechos = set()
        # Vigilar en paralelo a la camara; conversion no reinicia la captura.
        with subprocess.Popen(comando) as proceso:
            try:
                while True:
                    terminado = proceso.poll() is not None
                    ahora = time.monotonic()
                    for archivo in sorted(sesion.glob('parte_*.h264')):
                        vistos.setdefault(archivo,ahora)
                    orden = sorted(vistos)
                    for i, archivo in enumerate(orden):
                        cerrado = i+1 < len(orden) or terminado
                        if archivo in hechos or not cerrado:
                            continue
                        if terminado and proceso.returncode != 0:
                            raise RuntimeError(f'rpicam termino con codigo {proceso.returncode}; brutos conservados')
                        fin = vistos[orden[i+1]] if i+1 < len(orden) else ahora
                        if archivo.stat().st_size == 0:
                            hechos.add(archivo)
                            print('Segmento vacio conservado:',archivo,flush=True)
                            continue
                        finalizar(db,carpeta,archivo,vistos[archivo],fin,boot,origen,utc)
                        hechos.add(archivo)
                    if terminado:
                        break
                    if shutil.disk_usage(carpeta).free < 512*1024**2:
                        raise RuntimeError('Espacio insuficiente; detener captura')
                    time.sleep(0.1)
            finally:
                if proceso.poll() is None:
                    proceso.terminate()
                    try:
                        proceso.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        proceso.kill()
                        proceso.wait()
        print('Prueba de captura continua terminada. Revisar MP4 y JSON en',carpeta)
        if not vistos:
            raise RuntimeError('No se generaron segmentos')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Detenido. Los archivos brutos no procesados permanecen para revision.')
