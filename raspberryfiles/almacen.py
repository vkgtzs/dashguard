"""Base SQLite local y cola de registros por enviar."""
import hashlib
import json
import sqlite3
import time
import uuid
from pathlib import Path

TIPOS = ("sesion_inicio", "verificacion", "sesion_fin", "punto",
         "alerta", "evidencia", "comando_fallido")


def ahora_utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha_archivo(ruta):
    sha = hashlib.sha256()
    with Path(ruta).open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
            sha.update(bloque)
    return sha.hexdigest()


def abrir(ruta):
    db = sqlite3.connect(ruta, timeout=20)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=FULL")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS cola(
            orden INTEGER PRIMARY KEY AUTOINCREMENT,
            id TEXT UNIQUE NOT NULL,
            tipo TEXT NOT NULL,
            datos_json TEXT NOT NULL,
            creado TEXT NOT NULL,
            confirmado TEXT,
            rechazo TEXT);
        CREATE TABLE IF NOT EXISTS archivos(
            id TEXT PRIMARY KEY,
            ruta TEXT NOT NULL,
            tipo_mime TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            bytes INTEGER NOT NULL,
            confirmado TEXT);
        CREATE TABLE IF NOT EXISTS comandos_vistos(
            id TEXT PRIMARY KEY,
            visto TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS ajustes(
            clave TEXT PRIMARY KEY,
            valor_json TEXT NOT NULL);
    """)
    return db


def encolar(db, tipo, datos):
    if tipo not in TIPOS:
        raise ValueError("Tipo de registro desconocido: " + tipo)
    identificador = str(uuid.uuid4())
    with db:
        db.execute("INSERT INTO cola(id,tipo,datos_json,creado) VALUES(?,?,?,?)",
                   (identificador, tipo, json.dumps(datos, allow_nan=False), ahora_utc()))
    return identificador


def encolar_evidencia(db, ruta, tipo, datos):
    ruta = Path(ruta)
    mime = {"foto": "image/jpeg", "video": "video/mp4"}[tipo]
    identificador = str(uuid.uuid4())
    sha, tamano = sha_archivo(ruta), ruta.stat().st_size
    ficha = dict(datos, evidencia_id=identificador, tipo=tipo, sha256=sha, bytes=tamano)
    with db:
        db.execute("INSERT INTO archivos(id,ruta,tipo_mime,sha256,bytes) VALUES(?,?,?,?,?)",
                   (identificador, str(ruta), mime, sha, tamano))
        db.execute("INSERT INTO cola(id,tipo,datos_json,creado) VALUES(?,?,?,?)",
                   (str(uuid.uuid4()), "evidencia", json.dumps(ficha, allow_nan=False), ahora_utc()))
    return identificador


def archivos_pendientes(db, limite=5):
    return db.execute("SELECT * FROM archivos WHERE confirmado IS NULL LIMIT ?",
                      (limite,)).fetchall()


def confirmar_archivo(db, identificador):
    with db:
        db.execute("UPDATE archivos SET confirmado=? WHERE id=?", (ahora_utc(), identificador))


def registros_pendientes(db, limite=100):
    # La ficha de una evidencia se envia hasta que su archivo ya subio.
    return db.execute("""
        SELECT c.* FROM cola c
        WHERE c.confirmado IS NULL AND (
            c.tipo <> 'evidencia' OR EXISTS (
                SELECT 1 FROM archivos a
                WHERE a.id = json_extract(c.datos_json, '$.evidencia_id')
                  AND a.confirmado IS NOT NULL))
        ORDER BY c.orden LIMIT ?""", (limite,)).fetchall()


def confirmar_registros(db, identificadores):
    with db:
        db.executemany("UPDATE cola SET confirmado=? WHERE id=?",
                       [(ahora_utc(), i) for i in identificadores])


def apartar_rechazados(db, rechazados):
    with db:
        db.executemany("UPDATE cola SET confirmado=?, rechazo=? WHERE id=?",
                       [(ahora_utc(), r.get("motivo", "sin motivo"), r["id"]) for r in rechazados])


def comando_es_nuevo(db, identificador):
    with db:
        cursor = db.execute("INSERT OR IGNORE INTO comandos_vistos VALUES(?,?)",
                            (identificador, ahora_utc()))
    return cursor.rowcount == 1


def guardar_ajuste(db, clave, valor):
    with db:
        db.execute("INSERT INTO ajustes VALUES(?,?) ON CONFLICT(clave) DO UPDATE SET valor_json=excluded.valor_json",
                   (clave, json.dumps(valor)))


def leer_ajuste(db, clave, predeterminado=None):
    fila = db.execute("SELECT valor_json FROM ajustes WHERE clave=?", (clave,)).fetchone()
    return json.loads(fila[0]) if fila else predeterminado
