/*
 * DashGuard - control de energia con ESP32-C3
 *
 * El MPU-6050 esta conectado al ESP32-C3. Con el vehiculo detenido, el ESP duerme
 * (deep sleep) y el MPU queda en modo de bajo consumo con deteccion de movimiento:
 * su pin INT despierta al ESP.
 *
 * Al despertar, el ESP confirma que es un viaje (movimiento en varios segundos, no
 * solo un golpe de puerta) y despierta a la Raspberry con un pulso en su GPIO3.
 * Mientras la Raspberry esta encendida, el ESP le indica si hay movimiento por una
 * linea digital. La Raspberry decide cuando apagarse (20 min sin movimiento); al
 * verla apagada y sin movimiento, el ESP vuelve a dormir.
 *
 * Conexiones (ESP32-C3 SuperMini):
 *   GPIO6  <-> MPU SDA            GPIO7  <-> MPU SCL
 *   GPIO4  <-  MPU INT            (despierta al ESP; debe ser GPIO0-5)
 *   GPIO5  ->  Pi GPIO3, pin 5    (drenador abierto: pulso bajo despierta a la Pi apagada)
 *   GPIO10 ->  Pi GPIO5, pin 29   (alto = hay movimiento)
 *   GPIO1  <-  Pi GPIO13, pin 33  (alto = DashGuard corriendo en la Pi; 20 kOhm a GND)
 *   5V     <-  Pi pin 2 (5V)      GND <-> Pi pin 25 y MPU GND     3V3 -> MPU VCC
 */
#include <math.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>

#include "driver/gpio.h"
#include "driver/i2c_master.h"
#include "esp_log.h"
#include "esp_sleep.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "dashguard";

/* Pines */
#define PIN_SDA             6
#define PIN_SCL             7
#define PIN_INT_MPU         4
#define PIN_DESPERTAR_PI    5
#define PIN_MOVIMIENTO      10
#define PIN_PI_ENCENDIDA    1

/* MPU-6050 */
#define MPU_DIRECCION       0x68
#define REG_MOT_THR         0x1F
#define REG_MOT_DUR         0x20
#define REG_CONFIG          0x1A
#define REG_GYRO_CONFIG     0x1B
#define REG_ACCEL_CONFIG    0x1C
#define REG_INT_PIN_CFG     0x37
#define REG_INT_ENABLE      0x38
#define REG_INT_STATUS      0x3A
#define REG_ACCEL_XOUT_H    0x3B
#define REG_MOT_DETECT_CTRL 0x69
#define REG_PWR_MGMT_1      0x6B
#define REG_PWR_MGMT_2      0x6C
#define REG_WHO_AM_I        0x75

/* Deteccion de movimiento con el ESP despierto (mismos criterios que la Raspberry) */
#define GRAVEDAD                9.80665f
#define UMBRAL_ACEL_MS2         0.6f    /* desviacion de la magnitud respecto a 1 g */
#define UMBRAL_GIRO_GRADOS_S    8.0f
#define PERIODO_MS              100
#define VENTANA_MUESTRAS        10      /* 1 s de muestras */
#define MINIMO_EN_VENTANA       2       /* muestras con movimiento dentro de la ventana */
#define RETENCION_MOVIMIENTO_MS 2000    /* la linea sigue en alto tras el ultimo movimiento */

/* Deteccion con el ESP dormido (registros del MPU) */
#define MOT_UMBRAL              20      /* x 2 mg = 40 mg */
#define MOT_DURACION_MS         20

/* Encendido y apagado */
#define SEGUNDOS_PARA_VIAJE     3       /* segundos con movimiento para despertar a la Pi */
#define VENTANA_CONFIRMAR_MS    15000   /* con la Pi apagada, si no se confirma un viaje en este tiempo, dormir */
#define PULSO_DESPERTAR_MS      200
#define ESPERA_ARRANQUE_PI_MS   90000   /* tiempo para que la Pi arranque antes de otro pulso */
#define MAX_PULSOS              3
#define PI_APAGADA_CONFIRMAR_MS 30000   /* la Pi debe verse apagada este tiempo */
#define QUIETO_PARA_DORMIR_MS   60000
#define REINTENTO_SIN_MPU_US    (5ULL * 60 * 1000000)
#define REPORTE_ESTADO_MS       2000    /* linea de estado en el monitor */

/* Se conservan durante el deep sleep */
RTC_DATA_ATTR static float offset_giro[3];
RTC_DATA_ATTR static bool giro_calibrado;

static i2c_master_bus_handle_t bus_i2c;
static i2c_master_dev_handle_t mpu;

typedef struct {
    float ax, ay, az;   /* m/s2 */
    float gx, gy, gz;   /* grados/s, ya sin offset */
} lectura_t;

static int64_t ahora_ms(void)
{
    return esp_timer_get_time() / 1000;
}

static esp_err_t mpu_escribir(uint8_t registro, uint8_t valor)
{
    uint8_t datos[2] = {registro, valor};
    return i2c_master_transmit(mpu, datos, sizeof(datos), 100);
}

static esp_err_t mpu_leer(uint8_t registro, uint8_t *datos, size_t cantidad)
{
    return i2c_master_transmit_receive(mpu, &registro, 1, datos, cantidad, 100);
}

static void iniciar_gpio(void)
{
    /* Primero el nivel y despues el modo, para no mandar un pulso falso a la Pi */
    gpio_set_level(PIN_DESPERTAR_PI, 1);
    gpio_config_t despertar = {
        .pin_bit_mask = 1ULL << PIN_DESPERTAR_PI,
        .mode = GPIO_MODE_OUTPUT_OD,
    };
    ESP_ERROR_CHECK(gpio_config(&despertar));

    gpio_set_level(PIN_MOVIMIENTO, 0);
    gpio_config_t movimiento = {
        .pin_bit_mask = 1ULL << PIN_MOVIMIENTO,
        .mode = GPIO_MODE_OUTPUT,
    };
    ESP_ERROR_CHECK(gpio_config(&movimiento));

    gpio_config_t entradas = {
        .pin_bit_mask = (1ULL << PIN_PI_ENCENDIDA) | (1ULL << PIN_INT_MPU),
        .mode = GPIO_MODE_INPUT,
        .pull_down_en = GPIO_PULLDOWN_ENABLE,
    };
    ESP_ERROR_CHECK(gpio_config(&entradas));
}

static void iniciar_i2c(void)
{
    i2c_master_bus_config_t config_bus = {
        .i2c_port = -1,
        .sda_io_num = PIN_SDA,
        .scl_io_num = PIN_SCL,
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .glitch_ignore_cnt = 7,
        .flags.enable_internal_pullup = true,
    };
    ESP_ERROR_CHECK(i2c_new_master_bus(&config_bus, &bus_i2c));
    i2c_device_config_t config_mpu = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = MPU_DIRECCION,
        .scl_speed_hz = 400000,
    };
    ESP_ERROR_CHECK(i2c_master_bus_add_device(bus_i2c, &config_mpu, &mpu));
}

static bool mpu_presente(void)
{
    uint8_t identidad = 0;
    return mpu_leer(REG_WHO_AM_I, &identidad, 1) == ESP_OK && identidad == 0x68;
}

/* Lecturas continuas: acelerometro +-2 g, giroscopio +-250 grados/s, filtro de 44 Hz */
static esp_err_t mpu_modo_activo(void)
{
    esp_err_t error = ESP_OK;
    error |= mpu_escribir(REG_PWR_MGMT_1, 0x01);    /* despierto, reloj del giroscopio X */
    error |= mpu_escribir(REG_PWR_MGMT_2, 0x00);    /* todos los ejes encendidos */
    error |= mpu_escribir(REG_CONFIG, 0x03);
    error |= mpu_escribir(REG_GYRO_CONFIG, 0x00);
    error |= mpu_escribir(REG_ACCEL_CONFIG, 0x01);  /* +-2 g; filtro pasa altas de 5 Hz para la deteccion */
    error |= mpu_escribir(REG_INT_ENABLE, 0x00);
    vTaskDelay(pdMS_TO_TICKS(50));
    return error;
}

/* Bajo consumo: solo acelerometro a 5 Hz, interrupcion de movimiento en INT */
static esp_err_t mpu_modo_vigilancia(void)
{
    esp_err_t error = ESP_OK;
    uint8_t estado;
    error |= mpu_escribir(REG_PWR_MGMT_1, 0x00);
    error |= mpu_escribir(REG_ACCEL_CONFIG, 0x01);
    error |= mpu_escribir(REG_MOT_THR, MOT_UMBRAL);
    error |= mpu_escribir(REG_MOT_DUR, MOT_DURACION_MS);
    error |= mpu_escribir(REG_MOT_DETECT_CTRL, 0x15);
    error |= mpu_escribir(REG_INT_PIN_CFG, 0x30);   /* INT activo en alto, se mantiene hasta leerse */
    error |= mpu_escribir(REG_INT_ENABLE, 0x40);    /* solo interrupcion de movimiento */
    vTaskDelay(pdMS_TO_TICKS(20));
    error |= mpu_escribir(REG_PWR_MGMT_2, 0x47);    /* despertar a 5 Hz, giroscopio apagado */
    error |= mpu_escribir(REG_PWR_MGMT_1, 0x20);    /* modo ciclo */
    vTaskDelay(pdMS_TO_TICKS(50));
    error |= mpu_leer(REG_INT_STATUS, &estado, 1);  /* limpia una interrupcion previa */
    return error;
}

static int16_t entero16(const uint8_t *datos)
{
    return (int16_t)((datos[0] << 8) | datos[1]);
}

static bool mpu_leer_datos(lectura_t *lectura)
{
    uint8_t datos[14];
    if (mpu_leer(REG_ACCEL_XOUT_H, datos, sizeof(datos)) != ESP_OK) {
        return false;
    }
    lectura->ax = entero16(&datos[0]) / 16384.0f * GRAVEDAD;
    lectura->ay = entero16(&datos[2]) / 16384.0f * GRAVEDAD;
    lectura->az = entero16(&datos[4]) / 16384.0f * GRAVEDAD;
    lectura->gx = entero16(&datos[8]) / 131.0f - offset_giro[0];
    lectura->gy = entero16(&datos[10]) / 131.0f - offset_giro[1];
    lectura->gz = entero16(&datos[12]) / 131.0f - offset_giro[2];
    return true;
}

/* El sensor debe estar quieto: se llama al primer encendido y antes de cada deep sleep */
static void calibrar_giro(void)
{
    float suma[3] = {0};
    int validas = 0;
    float respaldo[3] = {offset_giro[0], offset_giro[1], offset_giro[2]};
    offset_giro[0] = offset_giro[1] = offset_giro[2] = 0;
    for (int i = 0; i < 200; i++) {
        lectura_t lectura;
        if (mpu_leer_datos(&lectura)) {
            suma[0] += lectura.gx;
            suma[1] += lectura.gy;
            suma[2] += lectura.gz;
            validas++;
        }
        vTaskDelay(pdMS_TO_TICKS(10));  /* 1 tick: con FreeRTOS a 100 Hz, 5 ms redondea a 0 */
    }
    if (validas < 150) {
        offset_giro[0] = respaldo[0];
        offset_giro[1] = respaldo[1];
        offset_giro[2] = respaldo[2];
        ESP_LOGW(TAG, "Calibracion fallida; se conservan los offsets anteriores");
        return;
    }
    for (int eje = 0; eje < 3; eje++) {
        offset_giro[eje] = suma[eje] / validas;
    }
    giro_calibrado = true;
    ESP_LOGI(TAG, "Giroscopio calibrado: %.2f %.2f %.2f", offset_giro[0], offset_giro[1], offset_giro[2]);
}

static bool hay_movimiento(const lectura_t *l)
{
    float magnitud = sqrtf(l->ax * l->ax + l->ay * l->ay + l->az * l->az);
    float giro = fmaxf(fabsf(l->gx), fmaxf(fabsf(l->gy), fabsf(l->gz)));
    return fabsf(magnitud - GRAVEDAD) > UMBRAL_ACEL_MS2 || giro > UMBRAL_GIRO_GRADOS_S;
}

static bool pi_encendida(void)
{
    return gpio_get_level(PIN_PI_ENCENDIDA) == 1;
}

static void despertar_pi(void)
{
    ESP_LOGI(TAG, "Despertando a la Raspberry");
    gpio_set_level(PIN_DESPERTAR_PI, 0);
    vTaskDelay(pdMS_TO_TICKS(PULSO_DESPERTAR_MS));
    gpio_set_level(PIN_DESPERTAR_PI, 1);
}

static void dormir(void)
{
    gpio_set_level(PIN_MOVIMIENTO, 0);
    if (mpu_modo_vigilancia() != ESP_OK) {
        ESP_LOGE(TAG, "No se pudo preparar el MPU; se reintentara en 5 min");
        esp_sleep_enable_timer_wakeup(REINTENTO_SIN_MPU_US);
    } else {
        ESP_ERROR_CHECK(esp_deep_sleep_enable_gpio_wakeup(1ULL << PIN_INT_MPU, ESP_GPIO_WAKEUP_GPIO_HIGH));
    }
    ESP_LOGI(TAG, "A dormir hasta detectar movimiento");
    /* El USB se apaga al dormir: dar tiempo a que salgan los ultimos mensajes */
    fflush(stdout);
    vTaskDelay(pdMS_TO_TICKS(200));
    esp_deep_sleep_start();
}

void app_main(void)
{
    iniciar_gpio();
    iniciar_i2c();

    int intentos_mpu = 0;
    while (!mpu_presente() || mpu_modo_activo() != ESP_OK) {
        ESP_LOGE(TAG, "MPU-6050 no responde");
        if (++intentos_mpu >= 3) {
            ESP_LOGE(TAG, "Se reintentara en 5 min");
            fflush(stdout);
            vTaskDelay(pdMS_TO_TICKS(200));
            esp_sleep_enable_timer_wakeup(REINTENTO_SIN_MPU_US);
            esp_deep_sleep_start();
        }
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
    if (!giro_calibrado) {
        ESP_LOGI(TAG, "Primer encendido: calibrando giroscopio, no mover");
        calibrar_giro();
    }

    bool ventana[VENTANA_MUESTRAS] = {false};
    int indice = 0, en_ventana = 0;

    int64_t ultimo_movimiento = -RETENCION_MOVIMIENTO_MS - 1;
    int64_t ultimo_segundo_contado = -1;
    int segundos_con_movimiento = 0;   /* del viaje que aun no despierta a la Pi */
    int64_t pi_apagada_desde = pi_encendida() ? -1 : ahora_ms();
    int64_t ultimo_pulso = -ESPERA_ARRANQUE_PI_MS - 1;
    int pulsos = 0;
    int64_t ultimo_reporte = 0;

    while (true) {
        int64_t t = ahora_ms();

        lectura_t lectura;
        bool leida = mpu_leer_datos(&lectura);
        bool muestra = leida && hay_movimiento(&lectura);
        en_ventana += (int)muestra - (int)ventana[indice];
        ventana[indice] = muestra;
        indice = (indice + 1) % VENTANA_MUESTRAS;

        bool moviendose = en_ventana >= MINIMO_EN_VENTANA;
        if (moviendose) {
            ultimo_movimiento = t;
            if (t / 1000 != ultimo_segundo_contado) {
                ultimo_segundo_contado = t / 1000;
                segundos_con_movimiento++;
            }
        }
        gpio_set_level(PIN_MOVIMIENTO, t - ultimo_movimiento <= RETENCION_MOVIMIENTO_MS);

        bool encendida = pi_encendida();

        if (t - ultimo_reporte >= REPORTE_ESTADO_MS) {
            ultimo_reporte = t;
            if (leida) {
                float magnitud = sqrtf(lectura.ax * lectura.ax + lectura.ay * lectura.ay + lectura.az * lectura.az);
                float giro = fmaxf(fabsf(lectura.gx), fmaxf(fabsf(lectura.gy), fabsf(lectura.gz)));
                ESP_LOGI(TAG, "acel %.2f m/s2 (desvio %.2f) | giro %.1f g/s | movimiento %s | seg viaje %d | Pi %s",
                         magnitud, fabsf(magnitud - GRAVEDAD), giro, moviendose ? "SI" : "no",
                         segundos_con_movimiento, encendida ? "encendida" : "apagada");
            } else {
                ESP_LOGW(TAG, "No se pudo leer el MPU");
            }
        }
        if (encendida) {
            pi_apagada_desde = -1;
            segundos_con_movimiento = 0;
            pulsos = 0;
        } else if (pi_apagada_desde < 0) {
            pi_apagada_desde = t;
            ESP_LOGI(TAG, "La Raspberry se apago");
        }

        bool esperando_arranque = t - ultimo_pulso < ESPERA_ARRANQUE_PI_MS;
        if (!encendida && segundos_con_movimiento >= SEGUNDOS_PARA_VIAJE &&
            !esperando_arranque && pulsos < MAX_PULSOS) {
            despertar_pi();
            ultimo_pulso = ahora_ms();
            pulsos++;
        }

        bool quieto = t - ultimo_movimiento > QUIETO_PARA_DORMIR_MS;
        bool apagada_un_rato = !encendida && t - pi_apagada_desde > PI_APAGADA_CONFIRMAR_MS;
        /* Se cuenta desde que la Pi se ve apagada: al despertar, o despues de que la Pi se apago.
           Un reinicio breve del servicio en la Pi no alcanza a cumplir la ventana. */
        bool sin_viaje = !encendida && pulsos == 0 && t - pi_apagada_desde > VENTANA_CONFIRMAR_MS &&
                         segundos_con_movimiento < SEGUNDOS_PARA_VIAJE;
        bool pi_no_arranco = !encendida && pulsos >= MAX_PULSOS && !esperando_arranque;

        if (sin_viaje) {
            ESP_LOGI(TAG, "Fue un movimiento aislado, no un viaje");
            dormir();
        }
        if ((apagada_un_rato && quieto && !esperando_arranque) || pi_no_arranco) {
            if (pi_no_arranco) {
                ESP_LOGW(TAG, "La Raspberry no arranco despues de %d pulsos", pulsos);
            }
            calibrar_giro();
            dormir();
        }

        vTaskDelay(pdMS_TO_TICKS(PERIODO_MS));
    }
}
