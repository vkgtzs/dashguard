"""Envio de la cola local al backend."""
import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import almacen


def configurar(ruta):
    # dispositivo.json: backend, dispositivo_id, token
    config = json.loads(Path(ruta).read_text(encoding="utf-8-sig"))
    url = urlsplit(config["backend"])
    local = url.hostname in ("localhost", "127.0.0.1")
    if (url.scheme != "https" and not (url.scheme == "http" and local)) or not url.hostname \
            or url.username or url.password or url.query or url.fragment or url.path not in ("", "/"):
        raise ValueError("backend debe ser un origen HTTPS, sin credenciales ni ruta")
    if len(config.get("token", "")) < 32:
        raise ValueError("Falta el token del dispositivo")
    return config


def _peticion(config, ruta, cuerpo=None, metodo="GET", tipo="application/json",
              sha=None, enviar=urlopen):
    cabeceras = {"Authorization": "Bearer " + config["token"]}
    if cuerpo is not None:
        cabeceras["Content-Type"] = tipo
    if sha:
        cabeceras["X-Content-Sha256"] = sha
    peticion = Request(config["backend"].rstrip("/") + ruta, data=cuerpo,
                       headers=cabeceras, method=metodo)
    with enviar(peticion, timeout=60) as respuesta:
        if respuesta.status != 200:
            raise ValueError("Respuesta HTTP inesperada " + str(respuesta.status))
        return json.load(respuesta)


def subir_archivos(db, config, enviar=urlopen):
    subidos = 0
    for fila in almacen.archivos_pendientes(db):
        ruta = Path(fila["ruta"])
        if not ruta.is_file() or almacen.sha_archivo(ruta) != fila["sha256"]:
            raise ValueError("Archivo local ausente o modificado: " + fila["id"])
        respuesta = _peticion(config, "/dispositivo/evidencias/" + fila["id"], ruta.read_bytes(),
                              metodo="PUT", tipo=fila["tipo_mime"], sha=fila["sha256"], enviar=enviar)
        if respuesta.get("id") != fila["id"] or respuesta.get("sha256") != fila["sha256"]:
            raise ValueError("El servidor no confirmo el archivo " + fila["id"])
        almacen.confirmar_archivo(db, fila["id"])
        subidos += 1
    return subidos


def enviar_registros(db, config, enviar=urlopen):
    filas = almacen.registros_pendientes(db)
    if not filas:
        return 0
    cuerpo = {"registros": [dict(id=f["id"], tipo=f["tipo"], datos=json.loads(f["datos_json"]))
                            for f in filas]}
    respuesta = _peticion(config, "/dispositivo/registros", json.dumps(cuerpo).encode(),
                          metodo="POST", enviar=enviar)
    confirmados = respuesta.get("confirmados", [])
    rechazados = respuesta.get("rechazados", [])
    recibidos = confirmados + [r["id"] for r in rechazados]
    if sorted(recibidos) != sorted(f["id"] for f in filas):
        raise ValueError("Respuesta de lote incompleta; se reintentara")
    almacen.confirmar_registros(db, confirmados)
    if rechazados:
        almacen.apartar_rechazados(db, rechazados)
        print("Registros rechazados por el servidor:", rechazados, flush=True)
    return len(confirmados)


def una_vez(db, config, enviar=urlopen):
    return subir_archivos(db, config, enviar) + enviar_registros(db, config, enviar)


def consultar_estado(db, config, enviar=urlopen):
    estado = _peticion(config, "/dispositivo/estado", enviar=enviar)
    almacen.guardar_ajuste(db, "limite_velocidad_kmh", estado["limite_velocidad_kmh"])
    almacen.guardar_ajuste(db, "conductores", estado["conductores"])
    return [c for c in estado["comandos"] if almacen.comando_es_nuevo(db, c["id"])]
