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


class Bateria:
    """Lee el INA219 del UPS HAT. leer() devuelve None si no se puede leer."""

    CORRIENTE_CARGA_MA = 20  # corriente positiva: entra a la bateria

    def __init__(self):
        from smbus import SMBus

        self._bus = SMBus(1)

    def leer(self):
        import bateria

        try:
            voltaje, corriente_ma, porcentaje = bateria.leer(self._bus)
        except OSError:
            return None
        return dict(porcentaje=round(porcentaje), voltaje=round(voltaje, 2),
                    cargando=corriente_ma > self.CORRIENTE_CARGA_MA)

    def cerrar(self):
        self._bus.close()


class VigilanteBateria:
    """Decide la alerta y el apagado por bateria baja.

    actualizar() devuelve:
      "alerta"   la primera vez que baja de umbral_alerta sin cargador
      "rearmar"  cuando se conecta el cargador o sube, para volver a avisar en la siguiente descarga
      "apagar"   tras varias lecturas seguidas en umbral_apagado o menos sin cargador
      None       en otro caso
    Se piden varias lecturas seguidas porque el voltaje baja un momento con la carga
    (camara, Wi-Fi) y una sola lectura baja no significa bateria agotada.
    """

    def __init__(self, umbral_alerta=20, umbral_apagado=10, lecturas=3, alerta_enviada=False):
        self.umbral_alerta = umbral_alerta
        self.umbral_apagado = umbral_apagado
        self.lecturas = lecturas
        self.alerta_enviada = alerta_enviada
        self._bajas_alerta = 0
        self._bajas_apagado = 0

    def actualizar(self, porcentaje, cargando):
        if cargando or porcentaje > self.umbral_alerta + 5:
            self._bajas_alerta = self._bajas_apagado = 0
            if self.alerta_enviada:
                self.alerta_enviada = False
                return "rearmar"
            return None
        self._bajas_alerta = self._bajas_alerta + 1 if porcentaje <= self.umbral_alerta else 0
        self._bajas_apagado = self._bajas_apagado + 1 if porcentaje <= self.umbral_apagado else 0
        if self._bajas_apagado >= self.lecturas:
            return "apagar"
        if self._bajas_alerta >= self.lecturas and not self.alerta_enviada:
            self.alerta_enviada = True
            return "alerta"
        return None


def apagar_raspberry():
    # Requiere la regla de sudo de /etc/sudoers.d/dashguard-apagado
    subprocess.run(["sudo", "-n", "/usr/bin/systemctl", "poweroff"], check=True, timeout=30)
