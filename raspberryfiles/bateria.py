"""Nivel de bateria del UPS HAT (Seengreat Pi Zero UPS HAT A) por su INA219.

    python3 bateria.py          # una lectura
    python3 bateria.py --cada 5 # una lectura cada 5 s (Ctrl+C para salir)

El INA219 esta en el bus I2C 1, direccion 0x43. Con su configuracion de fabrica
mide sin calibrar el voltaje de la bateria (registro 0x02) y el voltaje en la
resistencia de medicion (registro 0x01), del que sale la corriente.
"""
import argparse
import time

DIRECCION = 0x43
REG_SHUNT = 0x01
REG_BUS = 0x02
RESISTENCIA_SHUNT_OHM = 0.01  # medido: con 0.1 la corriente salia 10 veces menor; afecta solo la corriente
VOLTAJE_VACIA = 3.0          # Li-po de 3.7 V: ~3.0 V descargada, 4.2 V llena
VOLTAJE_LLENA = 4.2


def leer_registro(bus, registro):
    valor = bus.read_word_data(DIRECCION, registro)
    return ((valor & 0xFF) << 8) | (valor >> 8)  # el INA219 envia el byte alto primero


def leer(bus):
    voltaje = (leer_registro(bus, REG_BUS) >> 3) * 0.004
    shunt = leer_registro(bus, REG_SHUNT)
    if shunt >= 0x8000:
        shunt -= 0x10000
    corriente_ma = shunt * 0.01 / RESISTENCIA_SHUNT_OHM  # 10 uV por unidad
    porcentaje = (voltaje - VOLTAJE_VACIA) / (VOLTAJE_LLENA - VOLTAJE_VACIA) * 100
    return voltaje, corriente_ma, max(0.0, min(100.0, porcentaje))


def main():
    from smbus import SMBus

    argumentos = argparse.ArgumentParser()
    argumentos.add_argument("--cada", type=float, help="segundos entre lecturas")
    opciones = argumentos.parse_args()
    bus = SMBus(1)  # el smbus de Raspberry Pi OS no se puede usar con "with"
    try:
        while True:
            voltaje, corriente_ma, porcentaje = leer(bus)
            estado = "cargando" if corriente_ma > 20 else "descargando" if corriente_ma < -20 else "estable"
            print(f"{time.strftime('%H:%M:%S')}  {porcentaje:5.1f} %  |  {voltaje:.2f} V  |  "
                  f"{corriente_ma:+.0f} mA ({estado})", flush=True)
            if not opciones.cada:
                break
            time.sleep(opciones.cada)
    except KeyboardInterrupt:
        pass
    finally:
        bus.close()


if __name__ == "__main__":
    main()
