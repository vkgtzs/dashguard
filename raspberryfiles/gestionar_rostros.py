"""Rostros de conductores desde la terminal de la Raspberry.

Lo normal es registrar rostros desde la app (Conductores > Registrar rostro).
Esta herramienta sirve para pruebas y para subir registros hechos antes.

    python3 gestionar_rostros.py registrar --id <uuid-del-conductor> --nombre "Nombre"
    python3 gestionar_rostros.py subir       # envia al servidor los rostros guardados en esta Pi
    python3 gestionar_rostros.py listar
    python3 gestionar_rostros.py verificar

Detener antes el servicio (systemctl --user stop dashguard) porque usa la misma camara.
Los rostros se envian al servidor la proxima vez que corra el servicio.
"""
import argparse
import re
import sys
import time

import almacen
import rostros
from dashguard import DB

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def encolar_subida(conductor_id, descriptores):
    DB.parent.mkdir(parents=True, exist_ok=True)
    db = almacen.abrir(DB)
    try:
        almacen.encolar(db, "rostro", dict(conductor_id=conductor_id, descriptores=descriptores))
    finally:
        db.close()


def registrar(conductor_id, nombre, muestras):
    if not UUID.match(conductor_id):
        sys.exit("El id debe ser el UUID del conductor en Supabase (en minusculas)")
    print(f"Mira a la camara. Se tomaran {muestras} muestras; mueve un poco la cabeza entre cada una.")
    try:
        descriptores = rostros.capturar_muestras(muestras)
    except RuntimeError as error:
        sys.exit(str(error).capitalize())
    conductores = rostros.cargar_conductores()
    conductores[conductor_id] = dict(nombre=nombre, descriptores=descriptores,
                                     registrado=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    rostros.guardar_conductores(conductores)
    encolar_subida(conductor_id, descriptores)
    print(f"Registrado: {nombre} ({conductor_id}). Se enviara al servidor al iniciar el servicio.")


def subir():
    conductores = rostros.cargar_conductores()
    if not conductores:
        sys.exit("No hay rostros guardados en esta Pi")
    for conductor_id, datos in conductores.items():
        encolar_subida(conductor_id, datos["descriptores"])
        print("En cola para subir:", datos["nombre"], conductor_id)


def listar():
    conductores = rostros.cargar_conductores()
    if not conductores:
        print("No hay conductores registrados")
    for conductor_id, datos in conductores.items():
        print(f"{conductor_id}  {datos['nombre']}  {len(datos['descriptores'])} muestras  {datos.get('registrado', '')}")


def verificar():
    conductores = rostros.cargar_conductores()
    print("Verificando... mira a la camara")
    resultado = rostros.verificar_en_camara()
    nombre = conductores.get(resultado["conductor_id"] or "", {}).get("nombre")
    print("Resultado:", resultado["resultado"], f"({nombre})" if nombre else "")
    for clave, valor in resultado.items():
        print(f"   {clave}: {valor}")


def main():
    argumentos = argparse.ArgumentParser()
    acciones = argumentos.add_subparsers(dest="accion", required=True)
    alta = acciones.add_parser("registrar")
    alta.add_argument("--id", required=True)
    alta.add_argument("--nombre", required=True)
    alta.add_argument("--muestras", type=int, default=rostros.MUESTRAS_REGISTRO)
    acciones.add_parser("subir")
    acciones.add_parser("listar")
    acciones.add_parser("verificar")
    opciones = argumentos.parse_args()

    if opciones.accion == "registrar":
        registrar(opciones.id.lower(), opciones.nombre, opciones.muestras)
    elif opciones.accion == "subir":
        subir()
    elif opciones.accion == "listar":
        listar()
    else:
        verificar()


if __name__ == "__main__":
    main()
