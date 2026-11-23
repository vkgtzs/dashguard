# DashGuard - control de energía (ESP32-C3)

El ESP32-C3 vigila el movimiento con el MPU-6050 y duerme en deep sleep mientras el
vehículo está detenido. Al detectar un viaje despierta a la Raspberry; la Raspberry se
apaga sola tras 20 min sin movimiento y el ESP vuelve a dormir.

## Conexiones

| ESP32-C3 | Conecta a | Uso |
|---|---|---|
| GPIO6 | MPU SDA | I2C |
| GPIO7 | MPU SCL | I2C |
| GPIO4 | MPU INT | Despierta al ESP (debe ser GPIO0-5) |
| GPIO5 | Pi GPIO3 (pin 5) | Pulso bajo que despierta a la Pi apagada |
| GPIO10 | Pi GPIO5 (pin 29) | Alto = hay movimiento |
| GPIO1 | Pi GPIO13 (pin 33) | Alto = DashGuard corriendo; resistencia de 20 kΩ a GND |
| 3V3 | MPU VCC | |
| 5V | Pi pin 2 (5V) | Alimentación del ESP |
| GND | Pi pin 25 y MPU GND | Tierra común |

## Compilar y cargar (ESP-IDF 5.3 o posterior)

    idf.py set-target esp32c3
    idf.py build
    idf.py -p COM5 flash monitor

Al primer encendido el ESP calibra el giroscopio: el dispositivo debe estar quieto.
