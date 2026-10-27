"""Cola persistente SQLite -> API. Solo biblioteca estandar; no usa claves Supabase."""
import argparse
import json
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def ahora():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def abrir(ruta):
    # No crear una base vacia por un error de ruta.
    db = sqlite3.connect(f"{ruta.resolve().as_uri()}?mode=rw", uri=True, timeout=10)
    db.row_factory = sqlite3.Row
    return db


def preparar(db):
    columnas = {f[1] for f in db.execute("PRAGMA table_info(muestras)")}
    if not {"id", "fecha_hora_pc", "datos_json"} <= columnas:
        raise ValueError("La base no tiene el formato esperado de muestras")
    if "muestra_id" not in columnas:
        respaldo = Path(args_db_path(db)).with_name("antes_sincronizacion.sqlite3")
        if respaldo.exists():
            raise ValueError(f"Ya existe {respaldo}; conserva ese respaldo antes de migrar")
        with closing(sqlite3.connect(respaldo)) as copia:
            db.backup(copia)
        print("Respaldo:", respaldo)

    with db:
        if "muestra_id" not in columnas:
            db.execute("ALTER TABLE muestras ADD COLUMN muestra_id TEXT")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS muestras_uuid ON muestras(muestra_id)")
        # Trigger persistente: el registrador anterior puede seguir insertando igual.
        db.execute("""
            CREATE TRIGGER IF NOT EXISTS asignar_uuid_muestra
            AFTER INSERT ON muestras WHEN NEW.muestra_id IS NULL
            BEGIN
                UPDATE muestras SET muestra_id =
                    lower(hex(randomblob(4))) || '-' ||
                    lower(hex(randomblob(2))) || '-4' ||
                    substr(lower(hex(randomblob(2))), 2) || '-' ||
                    substr('89ab', (random() & 3) + 1, 1) ||
                    substr(lower(hex(randomblob(2))), 2) || '-' ||
                    lower(hex(randomblob(6)))
                WHERE id = NEW.id;
            END
        """)
        pendientes = db.execute("SELECT id FROM muestras WHERE muestra_id IS NULL").fetchall()
        for fila in pendientes:
            db.execute("UPDATE muestras SET muestra_id=? WHERE id=?", (str(uuid.uuid4()), fila[0]))
        db.execute("""
            CREATE TABLE IF NOT EXISTS cola_sync (
                muestra_id TEXT PRIMARY KEY,
                muestra_local_id INTEGER NOT NULL UNIQUE,
                payload TEXT NOT NULL,
                enviada_fecha TEXT,
                servidor_id TEXT,
                ultimo_error TEXT
            )
        """)


def args_db_path(db):
    return db.execute("PRAGMA database_list").fetchone()[2]


def encolar(db, dispositivo):
    # La primera preparacion fija dispositivo y contenido para todos los reintentos.
    with db:
        filas = db.execute("""
            SELECT m.* FROM muestras m LEFT JOIN cola_sync c ON c.muestra_id=m.muestra_id
            WHERE c.muestra_id IS NULL ORDER BY m.id
        """).fetchall()
        for fila in filas:
            datos = json.loads(fila["datos_json"])
            # El contrato actual exige valor de aceleracion numerico. No inventar
            # ceros ni bloquear muestras sanas detras de filas solo GPS/fallo IMU.
            if (datos.get('imu_valida') is False or datos.get('prueba_fallo_imu') is True
                    or datos.get('magnitud_ms2') is None):
                continue
            valido = datos["gps_valido"]
            if not isinstance(valido, bool):
                raise ValueError(f"GPS invalido en muestra {fila['id']}")
            payload = {
                "device_id": dispositivo, "muestra_id": fila["muestra_id"],
                "fecha_hora": fila["fecha_hora_pc"], "recorrido_id": None,
                "variable": "aceleracion", "valor": datos["magnitud_ms2"],
                "unidad": "m/s2", "source": "mpu6050", "gps_valido": valido,
            }
            for campo in ("ax_ms2", "ay_ms2", "az_ms2", "gx_grados_s", "gy_grados_s", "gz_grados_s"):
                payload[campo] = datos[campo]
            for campo in ("latitud", "longitud", "satelites", "hdop", "velocidad_kmh"):
                payload[campo] = datos.get(campo) if valido else None
            db.execute("""INSERT INTO cola_sync (muestra_id, muestra_local_id, payload)
                          VALUES (?, ?, ?)""",
                       (fila["muestra_id"], fila["id"], json.dumps(payload, allow_nan=False)))


def resumen(db):
    total = db.execute("SELECT count(*) FROM muestras").fetchone()[0]
    en_cola, enviadas = db.execute(
        "SELECT count(*), coalesce(sum(enviada_fecha IS NOT NULL), 0) FROM cola_sync"
    ).fetchone()
    print(f"Muestras: {total} | Enviadas: {enviadas} | Pendientes: {en_cola - enviadas}")
    print(f"Sin encolar (incluye fallos IMU conservados localmente): {total - en_cola}")


def sincronizar(db, url, limite=100, enviar=None):
    enviar = enviar or urlopen
    filas = db.execute("SELECT * FROM cola_sync WHERE enviada_fecha IS NULL ORDER BY muestra_local_id LIMIT ?",
                       (limite,)).fetchall()
    for fila in filas:
        payload = json.loads(fila["payload"])
        request = Request(url, data=fila["payload"].encode("utf-8"),
                          headers={"Content-Type": "application/json"}, method="POST")
        try:
            with enviar(request, timeout=20) as respuesta:
                if respuesta.status not in (200, 201):
                    raise ValueError(f"HTTP inesperado: {respuesta.status}")
                resultado = json.load(respuesta)
                medicion = resultado.get("medicion", {})
                if (medicion.get("muestra_id") != fila["muestra_id"]
                        or medicion.get("device_id") != payload["device_id"]
                        or medicion.get("id") is None):
                    raise ValueError("El servidor no confirmo UUID, dispositivo e ID esperados")
            with db:
                db.execute("""UPDATE cola_sync SET enviada_fecha=?, servidor_id=?, ultimo_error=NULL
                              WHERE muestra_id=?""",
                           (ahora(), str(medicion["id"]), fila["muestra_id"]))
            print(f"Confirmada local #{fila['muestra_local_id']} -> servidor #{medicion['id']}")
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
            with db:
                db.execute("UPDATE cola_sync SET ultimo_error=? WHERE muestra_id=?",
                           (str(error)[:500], fila["muestra_id"]))
            print(f"No confirmada #{fila['muestra_local_id']}: {error}")
            print("Se conserva pendiente con el mismo UUID. Corrige la causa y vuelve a ejecutar.")
            return False
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path.home() / "dashguard/datos/dashguard.sqlite3")
    parser.add_argument("--device", default="dashguard-pi-001")
    parser.add_argument("--url", help="URL completa: http://IP_DEL_PC:3000/mediciones")
    parser.add_argument("--limite", type=int, default=100)
    argumentos = parser.parse_args()
    if not argumentos.device.strip() or argumentos.limite < 1:
        parser.error("device no puede estar vacio y limite debe ser positivo")
    if argumentos.url:
        url = urlsplit(argumentos.url)
        if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password or url.path != "/mediciones" or url.query or url.fragment:
            parser.error("Usa una URL HTTP(S) sin credenciales que termine en /mediciones")
    db = abrir(argumentos.db)
    try:
        preparar(db)
        encolar(db, argumentos.device.strip())
        resumen(db)
        if argumentos.url:
            correcto = sincronizar(db, argumentos.url, argumentos.limite)
            resumen(db)
            return 0 if correcto else 1
        print("Preparacion local completada; no se envio nada.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (sqlite3.Error, ValueError, OSError, KeyError) as error:
        print(f"ERROR: {error}")
        raise SystemExit(1)
