"""Limpieza conservadora: solo muestras confirmadas, antiguas y no vinculadas."""
import argparse
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path


def limpiar(db, dias=7, aplicar=False):
    limite = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()
    db.execute('BEGIN IMMEDIATE')
    try:
        vinculados = ''
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='video_muestras'").fetchone():
            vinculados = 'AND NOT EXISTS (SELECT 1 FROM video_muestras v WHERE v.muestra_id=m.muestra_id)'
        consulta = '''SELECT m.id, m.muestra_id FROM muestras m JOIN cola_sync c
            ON c.muestra_id=m.muestra_id AND c.muestra_local_id=m.id
            WHERE c.enviada_fecha IS NOT NULL
            AND julianday(m.fecha_hora_pc) < julianday(?)
            AND julianday(c.enviada_fecha) < julianday(?) ''' + vinculados
        candidatas = db.execute(consulta, (limite, limite)).fetchall()
        if aplicar:
            for identificador, muestra_id in candidatas:
                db.execute('DELETE FROM cola_sync WHERE muestra_id=?', (muestra_id,))
                db.execute('DELETE FROM muestras WHERE id=?', (identificador,))
        db.commit()
        return len(candidatas)
    except BaseException:
        db.rollback()
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--aplicar', action='store_true')
    a = p.parse_args()
    ruta = Path.home() / 'dashguard/datos/dashguard.sqlite3'
    with closing(sqlite3.connect(f'{ruta.as_uri()}?mode=rw', uri=True, timeout=10)) as db:
        print('Eliminadas:' if a.aplicar else 'Candidatas (sin borrar):', limpiar(db, aplicar=a.aplicar))
    print('Las paginas libres de SQLite se reutilizan; no se ejecuta VACUUM en caliente.')
