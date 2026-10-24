import math
import time
from smbus import SMBus

DIRECCION = 0x68


def entero16(datos, inicio):
    valor = (datos[inicio] << 8) | datos[inicio + 1]
    return valor - 65536 if valor >= 32768 else valor


bus = SMBus(1)

try:
    # Despertar el sensor y configurar los rangos.
    bus.write_byte_data(DIRECCION, 0x6B, 0x00)
    time.sleep(0.1)
    bus.write_byte_data(DIRECCION, 0x1B, 0x00)  # ±250 grados/s
    bus.write_byte_data(DIRECCION, 0x1C, 0x00)  # ±2 g

    print("Calibrando: no muevas el sensor.")
    time.sleep(2)

    sumas = [0.0, 0.0, 0.0]
    for _ in range(500):
        datos_g = bus.read_i2c_block_data(DIRECCION, 0x43, 6)
        for eje, inicio in enumerate((0, 2, 4)):
            sumas[eje] += entero16(datos_g, inicio) / 131.0
        time.sleep(0.01)

    offsets = [suma / 500 for suma in sumas]
    print("Offsets [grados/s]:", offsets)
    print("Giroscopio calibrado. Ctrl+C para terminar.")

    while True:
        datos = bus.read_i2c_block_data(DIRECCION, 0x3B, 14)

        ax, ay, az = [
            entero16(datos, i) / 16384.0 * 9.80665
            for i in (0, 2, 4)
        ]
        gx, gy, gz = [
            entero16(datos, i) / 131.0
            for i in (8, 10, 12)
        ]

        gx -= offsets[0]
        gy -= offsets[1]
        gz -= offsets[2]
        magnitud = math.sqrt(ax**2 + ay**2 + az**2)

        print(
            f"A [m/s2]: {ax:7.2f} {ay:7.2f} {az:7.2f} "
            f"|A|: {magnitud:6.2f}  "
            f"G [grados/s]: {gx:7.2f} {gy:7.2f} {gz:7.2f}"
        )
        time.sleep(0.5)

except KeyboardInterrupt:
    print("\nPrueba terminada.")

finally:
    bus.close()
