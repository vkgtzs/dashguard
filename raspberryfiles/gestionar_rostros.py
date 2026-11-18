"""Registro y prueba de rostros de conductores en la Raspberry.

    python3 gestionar_rostros.py registrar --id <uuid-del-conductor> --nombre "Nombre"
    python3 gestionar_rostros.py listar
    python3 gestionar_rostros.py borrar --id <uuid-del-conductor>
    python3 gestionar_rostros.py verificar

Detener antes el servicio (systemctl --user stop dashguard) porque usa la misma camara.
"""
import argparse
import itertools
import re
import sys
import time

import camara
import rostros

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
SEGUNDOS_REGISTRO = 60
PAUSA_ENTRE_MUESTRAS_S = 0.8
CONSISTENCIA_MINIMA = 0.5  # similitud media entre muestras de la misma persona


def registrar(conductor_id, nombre, muestras):
    if not UUID.match(conductor_id):
        sys.exit("El id debe ser el UUID del conductor en Supabase (en minusculas)")
    modelo = rostros.Rostros()
    descriptores = []
    print(f"Mira a la camara. Se tomaran {muestras} muestras; mueve un poco la cabeza entre cada una.")
    inicio = time.monotonic()
    with camara.cuadros() as obtener_cuadro:
        while len(descriptores) < muestras and time.monotonic() - inicio < SEGUNDOS_REGISTRO:
            imagen = obtener_cuadro()
            cara, motivo = modelo.cara_principal(imagen)
            if cara is None:
                print("  ", motivo.replace("_", " "))
                time.sleep(0.3)
                continue
            descriptores.append(modelo.descriptor(imagen, cara))
            print(f"   muestra {len(descriptores)}/{muestras} (confianza {cara[14]:.2f})")
            time.sleep(PAUSA_ENTRE_MUESTRAS_S)
    if len(descriptores) < muestras:
        sys.exit(f"Solo se obtuvieron {len(descriptores)} muestras; revisa la luz y el encuadre")

    pares = [rostros.similitud(a, b) for a, b in itertools.combinations(descriptores, 2)]
    consistencia = sum(pares) / len(pares)
    print(f"Consistencia entre muestras: {consistencia:.3f}")
    if consistencia < CONSISTENCIA_MINIMA:
        sys.exit("Las muestras no parecen de la misma persona; repite el registro con una sola cara a la vista")

    conductores = rostros.cargar_conductores()
    conductores[conductor_id] = dict(nombre=nombre, descriptores=descriptores,
                                     registrado=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    rostros.guardar_conductores(conductores)
    print(f"Registrado: {nombre} ({conductor_id})")


def listar():
    conductores = rostros.cargar_conductores()
    if not conductores:
        print("No hay conductores registrados")
    for conductor_id, datos in conductores.items():
        print(f"{conductor_id}  {datos['nombre']}  {len(datos['descriptores'])} muestras  {datos.get('registrado', '')}")


def borrar(conductor_id):
    conductores = rostros.cargar_conductores()
    if conductores.pop(conductor_id, None) is None:
        sys.exit("No existe ese conductor")
    rostros.guardar_conductores(conductores)
    print("Borrado", conductor_id)


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
    alta.add_argument("--muestras", type=int, default=8)
    acciones.add_parser("listar")
    baja = acciones.add_parser("borrar")
    baja.add_argument("--id", required=True)
    acciones.add_parser("verificar")
    opciones = argumentos.parse_args()

    if opciones.accion == "registrar":
        registrar(opciones.id.lower(), opciones.nombre, opciones.muestras)
    elif opciones.accion == "listar":
        listar()
    elif opciones.accion == "borrar":
        borrar(opciones.id.lower())
    else:
        verificar()


if __name__ == "__main__":
    main()
