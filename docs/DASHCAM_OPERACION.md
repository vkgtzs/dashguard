# DashGuard como dashcam: operacion y recuperacion

Entrega del 28 de octubre de 2026. Consultar tambien
[resultados](dashcam-resultados-2026-10-28.md): distingue pruebas realizadas de pendientes.
La version facial queda aplazada; esta ruta no identifica personas ni incidentes.
El usuario mantiene por ahora modo de pruebas de 30 minutos por arranque. Para
el producto final pidio grabacion mientras exista alimentacion; activar ese modo
y su politica de almacenamiento queda como incremento posterior.

## Arquitectura instalada

Camara/GPS/IMU -> Raspberry -> SQLite y segmentos locales protegidos.
Al recuperar Internet: Raspberry -> backend HTTPS en Render -> tabla privada
`dashcam_registros` y bucket privado `dashguard-videos` en Supabase.
Windows solo sirve archivos del frontend. El backend de Windows no es necesario.

Fuente principal: repositorio `vkgtzs/dashguard`, carpetas raspberry/backend/frontend.
Render sigue conectado a `vkgtzs/dashguard-backend`: se publico una copia del backend
conservando su historial. Despliegue inicial de esta entrega: `589bf34`.
No copiar archivos .env reales al repositorio de despliegue.

## Uso habitual: Raspberry

1. Alimentar por micro-USB **PWR IN**. Conservar camara y sensores ya conectados.
2. Mantener el conjunto inmovil al menos los primeros diez segundos para calibrar.
3. El servicio inicia una captura de 1800 s, con segmentos de 300 s solicitados,
   1280x720, H264 a unos 2 Mbps y 15 fps nominales. La duracion del MP4 depende de
   fotogramas entregados; consultar PTS y el informe, no asumir duracion exacta.
4. No requiere SSH ni Internet. Sin GPS registra la falta de posicion; con fallo
   IMU conserva GPS y campos IMU nulos. La sincronizacion nueva admite esos datos.
5. Tras la ventana de grabacion termina de procesar los ultimos segmentos y cierra
   el recorrido. No vuelve a grabar automaticamente hasta otro arranque o inicio
   manual del servicio. No asumir que graba indefinidamente.
6. Mantener alimentacion y volver a Wi-Fi para enviar los pendientes. Un LED de
   encendido no certifica por si solo que la captura este funcionando.

Comprobar desde una sesion SSH autenticada:

```bash
systemctl --user status dashcam-captura.service dashcam-sync.service --no-pager -l
python3 ~/dashguard/app/dashcam_verificar.py
```

`inactive` en captura puede ser normal despues de finalizar; revisar estado del
recorrido (`completo`, `detenido`, `incompleto`, `interrumpido` o `error`).
Para otro recorrido sin reiniciar: `systemctl --user start dashcam-captura.service`.
Para detenerlo controladamente: `systemctl --user stop dashcam-captura.service`.
El cierre puede tardar al procesar el ultimo segmento. No cortar alimentacion.

Servicios anteriores `dashguard-captura` y `dashguard-sync` permanecen detenidos;
su timer sigue deshabilitado. No activar ambas generaciones simultaneamente.
`Linger=yes` permite el arranque de servicios de usuario sin iniciar SSH.

Para instalar otro release completo con dependencias y config privada ya presentes,
ejecutar `bash instalar_dashcam_usuario.sh` desde ese release. Conserva unidades
anteriores, deshabilita la generacion antigua y habilita la nueva sin iniciar
una captura por sorpresa. El cambio de enlace app conserva el directorio anterior.
El instalador no genera credenciales ni cambia contrasenas.

## Alimentacion y apagado

El usuario aporto INIU BI-B41, USB-A hacia PWR IN y cable marcado 2.1 A.
Referencia de Raspberry Pi: fuente de 5 V / 2.5 A para la familia Zero
([documentacion](https://www.raspberrypi.com/documentation/computers/getting-started.html)).
La combinacion concreta se debe evaluar en el ensayo con powerbank; el numero
del cable no demuestra estabilidad ni autonomia. No se midio corriente con instrumento.
No hay UPS, boton de apagado ni deteccion automatica de bateria agotada instalados.
No conectar la LiPo directamente ni alimentar simultaneamente desde dos fuentes.

Apagado con conexion recuperada, desde Raspberry:

```bash
systemctl --user stop dashcam-captura.service
sudo poweroff
```

Esperar el apagado y al menos 20–30 segundos antes de desconectar. Si se esta
fuera de Wi-Fi, conservar alimentacion hasta recuperar acceso para apagar.
No manipular terminal, cableado o camara mientras se conduce. Primera prueba
con el carro estacionado o en laboratorio; mantener equipo sujeto y ventilado.

## Consulta: Windows

Desde la raiz del repositorio:

```powershell
python -m http.server 8080 --bind 127.0.0.1 --directory frontend
```

Abrir [consulta local](http://127.0.0.1:8080/dashcam.html). Backend:
`https://dashguard-backend.onrender.com`. Introducir la clave **del propietario**,
no la de dispositivo ni la de Supabase. La pagina la mantiene solo en memoria.
`Cerrar consulta` borra esa referencia y los datos mostrados; enlaces de video ya
emitidos pueden seguir validos hasta cinco minutos. No compartir enlaces privados.

Seleccionar recorrido y despues segmento. `Actualizar recorrido` consulta datos
que hayan llegado durante la sincronizacion. Los conteos son parciales mientras
la Raspberry tenga pendientes. La prueba de API aparece como sintetica y no es
un recorrido real. La pagina historica index.html enlaza a la consulta nueva;
sus antiguas llamadas ya requieren autenticacion.

## Archivos locales y retencion

Codigo instalado: `~/dashguard/app` apunta a un directorio de release conservado.
Base: `~/dashguard/datos/dashguard.sqlite3` (WAL, confirmar cierre antes de copiarla
como respaldo; usar SQLite backup para respaldo en vivo).
Videos: `~/dashguard/videos/recorridos/<UUID>/`, con JSON por MP4 y salud.jsonl.
Config privada: `~/dashguard/config/dashcam.json`, permisos 600, solo token del
dispositivo. No contiene la clave administrativa Supabase ni la del propietario.

Cada recorrido dispone de limite operativo de 1024 MiB. A 2 Mbps, 30 minutos
rondan 450 MB decimales, mas metadatos y reserva temporal. Al iniciar se exige
limite +512 MiB libres. Durante captura se comprueba reserva de 256 MiB.
Es una comprobacion operativa, no una cuota dura del sistema de archivos.

Todos los MP4 nuevos se catalogan protegidos. **No se borran recorridos, muestras
ni videos por intentar o completar una subida.** Tampoco se aplica la limpieza
antigua de siete dias en esta ruta. Los brutos de segmentos convertidos y
comprobados se sustituyen por MP4 sin recodificar, como en el grabador anterior.
Si falta espacio se detiene conservando lo existente. Recorridos, pendientes,
backups y exportaciones pueden crecer: revisar disco antes de otra salida.

## Sincronizacion y seguridad

Cola SQLite inmutable con UUID, payload UTF-8 y SHA256 permanentes. Se envia solo
contra backend HTTPS. Confirmacion requiere UUID, dispositivo y hash; en videos
tambien tamano. UUID con otros datos produce conflicto, nunca sobrescritura.
Un segmento interrumpido se vuelve a subir completo; no hay reanudacion por bytes.
Segmentos habituales de 2–3 MiB, limite API/bucket de 8 MiB.

Registros tipo video se envian despues de confirmar su objeto. Si cae la red
o se pierde una respuesta, el siguiente intento conserva identidad y contenido.
El backend compara contenido existente. Servicio de sync reintenta sin borrar.
La cola nueva cubre los recorridos creados por este supervisor. La cola historica
`cola_sync`, muestras anteriores sin recorrido y videos de ensayos antiguos se
conservan; no se migran ni se mezclan automaticamente con la entrega de hoy.
Por eso cero pendientes de dashcam no certifica cero pendientes historicos.

Propietario: GET; dispositivo: POST/PUT, asociado a un unico device_id. Claves
diferentes y privadas. Sin ellas el backend no inicia; GET / solo expone version.
La tabla nueva tiene RLS y sin privilegios anon/authenticated; bucket no publico.
Render usa credencial de servidor Supabase. CORS solo permite frontend localhost.
Es acceso minimo para un propietario y un dispositivo, sin gestion multiusuario.

Render Free puede arrancar lentamente tras inactividad; el cliente admite hasta
120 s por peticion y conserva pendientes si falla. No se contrato ningun plan.

## Recuperacion y limites

No quitar alimentacion durante escritura. WAL y cierres de segmento ayudan,
pero no garantizan ausencia de corrupcion ante cortes bruscos.
Al encontrar un recorrido sin cierre se marca interrumpido, con cierre estimado
en la ultima marca conocida del **mismo boot_id**, sin inventar hora de desconexion.
Se conservan brutos y tiempos pendientes; no hay recuperacion automatica completa
del ultimo H264 parcial. Revisarlos antes de eliminar o declarar recorrido completo.

Sin RTC, el reloj del sistema al arrancar offline puede ser incorrecto. Inicio
y cierre guardan observacion NTP; muestras conservan fecha host, boot_id y
CLOCK_BOOTTIME. No se reescriben timestamps al recuperar Internet. La recepcion
en nube no es fecha de captura. GPS es el ultimo fix reciente, no captura por frame;
IMU incluye gravedad y se registra aproximadamente a 1 Hz.

No se probaron dias de operacion, resistencia a calor de automovil, agotamiento
de bateria ni desconexion fisica en caliente. No hay alertas remotas sin red.

## Ensayo offline controlado con reconexion

Se preparo, con sudo y autorizacion del usuario, `preparar_offline.sh`:
instala temporizador de sistema `dashcam-wifi-reconectar.timer`, lo habilita para
el siguiente arranque, apaga solo Wi-Fi de Raspberry y solicita apagado seguro.
Existe rescate a 120 s en el arranque actual si el apagado falla.

En el siguiente arranque, radio Wi-Fi permanece apagada. El servicio de usuario
graba sin SSH; a los 33 min del arranque el temporizador activa Wi-Fi y se
deshabilita a si mismo. No cambia SSID ni contrasenas. El PC conserva Internet.
No desenchufar para forzar una recuperacion. Si no reconecta, conservar
alimentacion y revisar localmente: `sudo nmcli radio wifi on`.

Despues comprobar: boot_id nuevo, NTP al inicio/cierre, estado completo, duracion,
fronteras de segmentos, SHA256, pendientes cero y timer de reconexion deshabilitado.
El script de preparacion se detiene si encuentra unidades existentes; revisarlas
antes de rearmar otro ensayo. No sobrescribir archivos del sistema a ciegas.

## Actualizacion a cinco minutos

Release preparado `release-dashcam-20261028b-5min`; conserva el release anterior.
El modo de ensayo sigue siendo de 1800 segundos. Durante la instalacion se mantiene
la captura detenida y deshabilitada; no reactivar el arranque sin comunicarlo.
Con cortes en fotogramas clave pueden variar las duraciones y existir un ultimo
archivo corto. No prometer exactamente seis archivos bajo cualquier interrupcion.
