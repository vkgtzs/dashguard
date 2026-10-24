# Registro y sincronizacion en Raspberry

`sincronizar.py` usa solo bibliotecas estandar. La base esperada es
`~/dashguard/datos/dashguard.sqlite3`, creada por dashguard_local.py.
La primera ejecucion crea antes_sincronizacion.sqlite3 como respaldo.
No borrar la base ni cola_sync: contienen los UUID y confirmaciones.

## Preparacion manual

Detener el registrador antes de la primera migracion:

```bash
python3 ~/sincronizar.py
python3 ~/sincronizar.py --url http://192.168.1.135:3000/mediciones
```

Las muestras nuevas reciben UUID desde un trigger SQLite persistente, incluso
con el registrador original. La cola fija el contenido y dispositivo al encolar.
La sincronizacion utiliza dashguard-pi-001; el ESP32 conserva dashguard-001.
Por ahora los recorridos se envian como null. Los errores dejan pendiente la
muestra y detienen ese intento. Los errores de formato/conflicto requieren
corregir la causa; no se descartan automaticamente registros problematicos.

## Temporizador de usuario

Copiar sincronizar.py y las dos unidades a la Raspberry. Instalar las unidades:

```bash
mkdir -p ~/.config/systemd/user
cp ~/dashguard-sync.service ~/dashguard-sync.timer ~/.config/systemd/user/
systemd-analyze --user verify ~/.config/systemd/user/dashguard-sync.service ~/.config/systemd/user/dashguard-sync.timer
systemctl --user daemon-reload
systemctl --user enable --now dashguard-sync.timer
sudo loginctl enable-linger "$USER"
```

enable-linger permite ejecutar servicios del usuario sin mantener SSH abierto
y despues de arrancar. El registro de sensores todavia se inicia manualmente.
El timer espera 30 segundos despues de terminar cada intento; no inicia una
segunda instancia mientras la primera siga activa. Cada intento envia hasta
100 pendientes. No ejecutar simultaneamente otra sincronizacion manual.

```bash
systemctl --user list-timers dashguard-sync.timer
journalctl --user -u dashguard-sync.service -n 30 --no-pager
systemctl --user disable --now dashguard-sync.timer
systemctl --user stop dashguard-sync.service
```

El timer apagado no cancela por si solo un envio que ya este ejecutandose;
el ultimo comando lo detiene. Si el servidor inserto pero no se recibio la
confirmacion, el siguiente intento reusa el UUID y el backend devuelve la fila.

Para cambiar servidor, crear ~/.config/dashguard/sync.env con:
`DASHGUARD_API_URL=https://servidor/mediciones`. Debe apuntar al backend nuevo;
Render todavia no ha sido actualizado. Cambiar la IP si cambia la direccion
local del PC. No poner claves Supabase aqui.

## Captura al encender

Copiar dashguard-captura.service a ~/.config/systemd/user/ y ejecutar:

```bash
systemd-analyze --user verify ~/.config/systemd/user/dashguard-captura.service
systemctl --user daemon-reload
systemctl --user enable --now dashguard-captura.service
sudo loginctl enable-linger "$USER"
```

Requiere ~/dashguard_local.py y sus dependencias smbus/serial ya probadas.
Detener cualquier captura manual antes de iniciar el servicio. No ejecutar
las pruebas individuales de GPS o IMU mientras el servicio usa los sensores.
Al arrancar se calibra de nuevo el giroscopio: mantener inmovil el sensor
durante la calibracion. Esto no implementa deteccion automatica de reposo,
recorridos ni inicio de video. La fecha al arrancar sin red sigue pendiente
de validacion; guardar UTC no garantiza que el reloj este sincronizado.

```bash
systemctl --user status dashguard-captura.service --no-pager -l
sudo journalctl _SYSTEMD_USER_UNIT=dashguard-captura.service -n 30 --no-pager
systemctl --user stop dashguard-captura.service
systemctl --user start dashguard-captura.service
systemctl --user disable --now dashguard-captura.service
```

SIGINT permite que el programa cierre el puerto GPS y SQLite al detenerse.
Si el programa termina, se reintenta hasta cinco inicios por 120 segundos.
Una detencion explicita con systemctl stop no provoca reinicio automatico.

## Pruebas locales del sincronizador

`python3 -m unittest discover -s . -p test_sincronizar.py -v`
usa SQLite temporal y respuestas HTTP simuladas. El timer requiere verificar
systemd y comprobar los logs en la Raspberry; no se ha instalado desde el PC.
