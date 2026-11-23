"""Enlace con el ESP32-C3 que vigila el movimiento y apagado automatico de la Raspberry.

- GPIO5 (pin 29), entrada: el ESP la pone en alto mientras hay movimiento.
- GPIO13 (pin 33), salida: en alto mientras DashGuard corre; al apagarse la Pi
  queda en bajo y el ESP puede dormir. Debe ser un GPIO del 9 al 27, que por
  defecto tienen resistencia hacia abajo; los GPIO 0-8 la tienen hacia arriba.
- El ESP despierta a la Pi apagada con un pulso en GPIO3 (pin 5); eso lo hace
  el firmware de la Raspberry, aqui no hace falta codigo.
"""
import subprocess
import time

PIN_MOVIMIENTO = 5
PIN_ENCENDIDA = 13


class EnlaceESP32:
    """Fuente de movimiento para DetectorMovimiento, en lugar de leer el MPU directamente."""

    def __init__(self, pin_movimiento=PIN_MOVIMIENTO, pin_encendida=PIN_ENCENDIDA):
        from gpiozero import DigitalInputDevice, DigitalOutputDevice

        self._movimiento = DigitalInputDevice(pin_movimiento, pull_up=False)
        self._encendida = DigitalOutputDevice(pin_encendida, initial_value=True)

    def leer(self):
        return dict(imu_valida=True, imu_error=None, movimiento=bool(self._movimiento.value))

    def cerrar(self):
        self._encendida.off()
        self._encendida.close()
        self._movimiento.close()


class ApagadoAutomatico:
    """Indica cuando apagar: sin movimiento ni recorrido abierto durante cierto tiempo.

    El tiempo empieza al iniciar, asi que la Pi siempre queda encendida al menos ese
    tiempo despues de arrancar.
    """

    def __init__(self, segundos, reloj=time.monotonic):
        self.segundos = segundos
        self._ultima_actividad = reloj()

    def actualizar(self, hay_movimiento, en_recorrido, ahora):
        if hay_movimiento or en_recorrido:
            self._ultima_actividad = ahora
            return False
        return ahora - self._ultima_actividad >= self.segundos


def apagar_raspberry():
    # Requiere la regla de sudo de /etc/sudoers.d/dashguard-apagado
    subprocess.run(["sudo", "-n", "/usr/bin/systemctl", "poweroff"], check=True, timeout=30)
