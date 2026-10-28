"""Estado offline y outbox inmutable. Sin credenciales ni red."""
import hashlib
import json
import sqlite3
import uuid
from pathlib import Path


def serializar(datos):
    return json.dumps(datos,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)


def sha_archivo(ruta):
    sha=hashlib.sha256()
    with Path(ruta).open('rb') as f:
        for bloque in iter(lambda:f.read(1024*1024),b''):
            sha.update(bloque)
    return sha.hexdigest()


def abrir(ruta):
    db=sqlite3.connect(ruta,timeout=20)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA synchronous=FULL')
    db.executescript('''
      CREATE TABLE IF NOT EXISTS dashcam_recorridos(
        id TEXT PRIMARY KEY, boot_id TEXT NOT NULL, inicio_ns INTEGER NOT NULL,
        ultimo_ns INTEGER NOT NULL, fin_ns INTEGER, estado TEXT NOT NULL,
        carpeta TEXT NOT NULL, fin_id TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS dashcam_outbox(
        id TEXT PRIMARY KEY, recorrido_id TEXT NOT NULL, tipo TEXT NOT NULL,
        contenido_json TEXT NOT NULL, sha256 TEXT NOT NULL, confirmado TEXT,
        ultimo_error TEXT);
      CREATE TABLE IF NOT EXISTS dashcam_archivos(
        id TEXT PRIMARY KEY, recorrido_id TEXT NOT NULL, ruta TEXT NOT NULL,
        sha256 TEXT NOT NULL, bytes INTEGER NOT NULL, confirmado TEXT);
    ''')
    return db


def encolar(db,id,recorrido,tipo,contenido):
    texto=serializar(contenido)
    sha=hashlib.sha256(texto.encode()).hexdigest()
    previo=db.execute('SELECT sha256,recorrido_id,tipo FROM dashcam_outbox WHERE id=?',(id,)).fetchone()
    if previo:
        if tuple(previo)!=(sha,recorrido,tipo): raise ValueError('UUID local reutilizado con contenido distinto')
        return
    db.execute('INSERT INTO dashcam_outbox(id,recorrido_id,tipo,contenido_json,sha256) VALUES(?,?,?,?,?)',
               (id,recorrido,tipo,texto,sha))


def recolectar(db,recorrido,fin_ns=None):
    trip=db.execute('SELECT * FROM dashcam_recorridos WHERE id=?',(recorrido,)).fetchone()
    final=fin_ns or 9223372036854775807
    muestras=db.execute('''SELECT m.* FROM muestras m LEFT JOIN dashcam_outbox o ON o.id=m.muestra_id
      WHERE m.boot_id=? AND m.boottime_ns>=? AND m.boottime_ns<=? AND o.id IS NULL ORDER BY m.id LIMIT 200''',
      (trip['boot_id'],trip['inicio_ns'],final)).fetchall()
    for m in muestras:
        encolar(db,m['muestra_id'],recorrido,'muestra',dict(fecha_hora=m['fecha_hora_pc'],
          boot_id=m['boot_id'],boottime_ns=m['boottime_ns'],datos=json.loads(m['datos_json'])))
    carpeta=Path(trip['carpeta'])
    for video in db.execute('SELECT * FROM videos_espacio WHERE boot_id=? AND inicio_ns>=?',
                             (trip['boot_id'],trip['inicio_ns'])).fetchall():
        ruta=carpeta/video['archivo']
        if not ruta.is_file() or ruta.resolve().parent!=carpeta.resolve(): continue
        if db.execute('SELECT 1 FROM dashcam_archivos WHERE id=?',(video['id'],)).fetchone():continue
        meta=json.loads(ruta.with_suffix('.json').read_text(encoding='utf-8'))
        sha=sha_archivo(ruta)
        db.execute('INSERT INTO dashcam_archivos(id,recorrido_id,ruta,sha256,bytes) VALUES(?,?,?,?,?)',
                   (video['id'],recorrido,str(ruta),sha,ruta.stat().st_size))
        encolar(db,video['id'],recorrido,'video',dict(metadata=meta,sha256=sha,bytes=ruta.stat().st_size))
    return len(muestras)


def cerrar(db,trip,fin_ns,estado,detalle):
    db.execute('UPDATE dashcam_recorridos SET fin_ns=?,estado=? WHERE id=?',(fin_ns,estado,trip['id']))
    encolar(db,trip['fin_id'],trip['id'],'fin',dict(estado=estado,boot_id=trip['boot_id'],
            fin_boottime_ns=fin_ns,**detalle))


def recuperar(db):
    # Invocar con bloqueo exclusivo de captura. No inventar hora de desconexion.
    for trip in db.execute("SELECT * FROM dashcam_recorridos WHERE estado='activo'").fetchall():
        while recolectar(db,trip['id'],trip['ultimo_ns'])==200: pass
        cerrar(db,trip,trip['ultimo_ns'],'interrumpido',dict(cierre_estimado=True,
            motivo='ejecucion_anterior_sin_cierre; conservar brutos para revision'))
    db.commit()
