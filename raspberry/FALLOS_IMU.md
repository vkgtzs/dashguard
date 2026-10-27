# Registro GPS independiente de la validez IMU

Instalar juntos dashguard_local.py, imu_segura.py y sincronizar.py. No modificar
archivos mientras se ejecuta captura. Mantener timer de envio pausado en desarrollo.

El GPS se inicia antes de configurar/calibrar la IMU. Tras inicializacion (unos
siete segundos), cada iteracion guarda GPS y estado IMU aunque falle I2C, WHO_AM_I,
SLEEP, rangos o bloque cero. Error de apertura del bus tampoco cancela GPS.
Un fallo de SQLite sigue siendo fatal: no se afirma tolerancia a fallo de disco.

IMU valida: imu_valida=true y campos numericos. Fallo: imu_valida=false,
imu_error explicito y los siete campos de IMU null, nunca ceros inventados.
Si ocurre durante funcionamiento se invalidan offsets y se exige reiniciar
captura con sensor inmovil tras revisar hardware. No hay despertar/recalibracion
automaticos que oculten el fallo. Se registra el estado cada segundo.
No se garantiza deteccion de todos los reinicios electricos posibles.

El sincronizador actualizado omite estas filas sin marcarlas enviadas ni borrarlas,
y continua con las sanas. La API actual exige valor numerico y no representa aun
mediciones solo GPS/incidencias. Por tanto estas filas son SOLO LOCALES por ahora,
conservadas tambien por retencion (carecen de confirmacion). Falta ampliar API,
esquema y cliente para sincronizarlas. No reactivar el sincronizador viejo.
Filas historicas sin imu_valida con magnitud valida conservan su compatibilidad.

Los JSON de video incluyen automaticamente los campos nuevos. Contar muestras
vinculadas no implica que tengan IMU valida; inspeccionar imu_valida/imu_error.
La falla del hilo GPS aun no se reconecta automaticamente; caducidad sigue 10 s.

## Prueba sin tocar cables

Con captura detenida y sincronizacion pausada:

```bash
python3 ~/dashguard_local.py --simular-fallo-imu
```

No accede a IMU en ese modo. Registra GPS y marca fallo_simulado y
prueba_fallo_imu=true. Dejar 15 s y Ctrl+C. Esos registros no se envian al backend.
Despues iniciar servicio normal y validar IMU/GPS. No desconectar sensor en caliente.
Prueba simulada no demuestra desconexion fisica; prueba hardware pendiente.

## Recuperar version anterior

Detener captura, restaurar respaldo de dashguard_local.py y sincronizar.py juntos.
No borrar muestras nuevas ni sustituir SQLite por copia antigua (perderia datos).
El sincronizador anterior no soporta filas sin aceleracion; conservar el nuevo
si estas filas siguen presentes, o revisar su migracion antes de volver atras.
