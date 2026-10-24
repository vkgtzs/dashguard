"""Prueba acotada: clips con telemetria, seis recientes y proteccion manual.

Reabre la camara por clip: existen pausas entre clips. No es aun grabacion
continua de produccion ni sincronizacion exacta por fotograma.
"""
import argparse
import json
import shutil
import sqlite3
import subprocess
import time
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from retencion import limpiar


def esquema(db):
    db.executescript('''
        CREATE TABLE IF NOT EXISTS videos_locales (
            id TEXT PRIMARY KEY, archivo TEXT UNIQUE NOT NULL,
            boot_id TEXT NOT NULL, inicio_mono REAL NOT NULL, fin_mono REAL NOT NULL,
            inicio_utc TEXT NOT NULL, protegido INTEGER NOT NULL DEFAULT 0,
            estado TEXT NOT NULL DEFAULT 'listo'
        );
        CREATE TABLE IF NOT EXISTS video_muestras (
            video_id TEXT NOT NULL, muestra_id TEXT NOT NULL,
            PRIMARY KEY(video_id, muestra_id)
        );
    ''')


def rotar(db, carpeta, conservar=6):
    # Solo rutas registradas dentro de esta carpeta de prueba; nunca otras carpetas.
    filas = db.execute("SELECT id,archivo FROM videos_locales WHERE protegido=0 AND estado='listo' ORDER BY rowid DESC").fetchall()
    for identificador, nombre in filas[conservar:]:
        archivo = carpeta / nombre
        if archivo.resolve().parent != carpeta.resolve():
            raise ValueError('Ruta fuera de la carpeta de prueba')
        for ruta in (archivo, archivo.with_suffix('.json')):
            ruta.unlink(missing_ok=True)
        with db:
            db.execute('DELETE FROM video_muestras WHERE video_id=?', (identificador,))
            db.execute('DELETE FROM videos_locales WHERE id=?', (identificador,))
        print('Rotado:', nombre, flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--clips', type=int, default=9)
    a = p.parse_args()
    if not 1 <= a.clips <= 30:
        p.error('Usa entre 1 y 30 clips para esta prueba')
    carpeta = Path.home() / 'dashguard/videos/loop_prueba'
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta_db = Path.home() / 'dashguard/datos/dashguard.sqlite3'
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    with closing(sqlite3.connect(f'{ruta_db.as_uri()}?mode=rw', uri=True, timeout=10)) as db:
        columnas = {c[1] for c in db.execute('PRAGMA table_info(muestras)')}
        if not {'boot_id', 'muestra_id'} <= columnas:
            raise RuntimeError('Instala el registrador actualizado y ejecuta su captura primero')
        esquema(db)
        for _ in range(a.clips):
            if shutil.disk_usage(carpeta).free < 512 * 1024**2:
                raise RuntimeError('Menos de 512 MiB libres: se detiene sin borrar evidencia protegida')
            identificador = str(uuid.uuid4())
            parcial = carpeta / (identificador + '.h264.part')
            final = carpeta / (identificador + '.mp4')
            inicio = time.monotonic()
            utc = datetime.now(timezone.utc).isoformat()
            subprocess.run(['rpicam-vid', '--nopreview', '--timeout', '10000',
                '--width', '1280', '--height', '720', '--framerate', '15',
                '--codec', 'h264', '--bitrate', '2000000', '--inline', '--intra', '15',
                '--output', str(parcial)], check=True)
            fin = time.monotonic()
            temporal = carpeta / (identificador + '.part.mp4')
            subprocess.run(['ffmpeg', '-v', 'error', '-n', '-fflags', '+genpts',
                '-r', '15', '-i', str(parcial), '-c:v', 'copy', '-movflags', '+faststart',
                str(temporal)], check=True)
            temporal.rename(final)
            # Ventana conservadora del proceso de captura, no limites de fotogramas.
            filas = db.execute('''SELECT muestra_id,fecha_hora_pc,monotonic_s,datos_json
                FROM muestras WHERE boot_id=? AND monotonic_s>=? AND monotonic_s<=?
                ORDER BY monotonic_s''', (boot, inicio, fin)).fetchall()
            telemetria = [dict(muestra_id=f[0], fecha_hora=f[1], monotonic_s=f[2],
                               datos=json.loads(f[3])) for f in filas]
            metadatos = dict(video_id=identificador, archivo=final.name, boot_id=boot,
                inicio_utc=utc, inicio_mono=inicio, fin_mono=fin,
                tipo_asociacion='ventana del proceso; no sincronizacion por fotograma',
                muestras=telemetria)
            final.with_suffix('.json').write_text(json.dumps(metadatos, ensure_ascii=False), encoding='utf-8')
            with db:
                db.execute('''INSERT INTO videos_locales
                    (id,archivo,boot_id,inicio_mono,fin_mono,inicio_utc) VALUES(?,?,?,?,?,?)''',
                    (identificador, final.name, boot, inicio, fin, utc))
                db.executemany('INSERT INTO video_muestras VALUES (?,?)',
                               [(identificador, f[0]) for f in filas if f[0]])
            parcial.unlink()
            print(f'Video {identificador}: {len(filas)} muestras vinculadas', flush=True)
            rotar(db, carpeta)
            print('Mediciones antiguas confirmadas eliminadas:', limpiar(db, aplicar=True), flush=True)
        print('Prueba terminada. Se conservan seis clips no protegidos y sus JSON.')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Prueba detenida; archivos parciales se conservan para revision.')
