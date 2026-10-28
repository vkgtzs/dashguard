# Dashcam offline: evidencia del 28 de octubre de 2026

## Implementado

- Supervisor de sensores y una camara; recorrido UUID persistente y cierre.
- Grabador conservador sin rotacion ni retencion de muestras; MP4 protegidos.
- Cola SQLite separada, payload/checksum inmutables y confirmaciones verificadas.
- API autenticada, roles separados y acceso solo al dispositivo configurado.
- Tabla nueva privada y bucket privado, migracion 003 aplicada y comprobada.
- Backend publicado en Render desde repositorio de despliegue, commit `589bf34`.
- Frontend servido solo en localhost, consulta de recorridos, muestras y MP4 privados.
- Servicios de usuario habilitados y Linger comprobado; temporizador viejo deshabilitado.

## Pruebas ya completadas

Python en Windows: 28 pruebas. Raspberry: 13 pruebas de cola, recuperacion,
informe de continuidad, IMU y grabador. Node: nueve pruebas aprobadas.
Incluyen simulacion de falta de red, confirmacion incorrecta, conflicto de UUID,
roles, ausencia de claves y conservacion local. No equivalen a corte fisico ni
a desconexion real Wi-Fi: esta ultima se evalua separadamente.

### Hardware integrado corto

Recorrido `9d80df2f-e466-4a1e-9c5f-ed5f460ed197`:

- Ventana solicitada de video: 60 s. Supervisor completo: 86.3 s, incluyendo
  calibracion, inicializacion y procesado final.
- Seis MP4, 14 863 327 bytes en conjunto, todos protegidos.
- 77 muestras, 77 GPS validas y 77 IMU validas.
- Inicio, cierre, muestras y videos: 85 registros confirmados en nube.
- Seis archivos confirmados directamente por Raspberry -> Render -> Supabase.
- Temperatura tras sync: 40.8 C; throttled=0x0 observado.
- Pagina localhost consulto ese recorrido y sus sensores desde Render.
- Se cargo y reprodujo un segmento privado desde Supabase: duracion 11 s,
  readyState=4, sin error de media y reproduccion activa observada.

### Reintentos reales contra nube

- Prueba sintetica de API conservada y marcada como tal. Doble POST deja una
  fila; cambio de contenido para el mismo UUID devuelve 409; lectura anonima 401.
- Reintento real de un MP4 ya confirmado: SHA256 coincide y siguen existiendo
  seis objetos en su recorrido. No se borro ni sobrescribio ningun archivo.

## Ensayo de 30 minutos con powerbank: captura validada

El usuario confirmo INIU BI-B41, USB-A a PWR IN, cable marcado 2.1 A.
Confirmo arranque con esa powerbank aproximadamente a las 08:27 de Tijuana.
Wi-Fi de Raspberry se apago antes del apagado controlado; se instalo reconexion
automatica a los 33 min del proximo arranque. PC mantiene Internet.

Recorrido real `cf5d3291-7105-45cd-9fbe-323e8c945830`. La Raspberry volvio sola
por Wi-Fi a los 33 min de un arranque nuevo. El temporizador quedo deshabilitado.

| Comprobacion | Resultado observado |
|---|---:|
| Estado de cierre | completo, sin error |
| Ventana solicitada de video | 1800 s |
| Tiempo del supervisor, incluida preparacion/cierre | 1829.950 s |
| MP4 conservados y protegidos | 164 |
| Volumen de video | 429.347 MiB |
| Fotogramas catalogados y verificados al convertir | 26 996 |
| Duracion MP4 nominal, suma de frames/15 | 1799.733 s (29:59.7) |
| Duracion aproximada por SensorTimestamp | 1799.393 s |
| Cadencia original | 15.0028 fps |
| Intervalo maximo entre frames observado | 66.818 ms |
| Huecos mayores de 100 ms / timestamps no crecientes | 0 / 0 |
| Fronteras discontinuas entre clips | 0 |
| Errores de integridad SHA256/tamano/catalogo | 0 |
| Brutos parciales pendientes | 0 |
| Muestras de sensores | 1820 |
| GPS valido / IMU valida | 1818 / 1820 |
| Observaciones de salud | 177 |
| Estado Wi-Fi en todas esas observaciones | down |
| NTP al inicio / cierre | false / false |
| Temperatura maxima muestreada | 60.148 C |
| Throttled observado | 0x0 |
| Memoria disponible minima | 210 380 KiB (205.45 MiB) |
| Carga maxima de un minuto | 1.965 |

El sistema arranco y grabo sin SSH ni red, alimentado por la INIU. El tiempo de
video efectivo se indica arriba; no se oculta la diferencia de cuatro frames
respecto a 1800*15. La carga no es porcentaje de CPU. No hubo reinicios durante
el recorrido conservado. La prueba valida esta combinacion en condiciones de
laboratorio, no horas dentro de un automovil caliente ni autonomia total.

Al reconectar, NTP volvio a sincronizar. Las fechas de captura no se reescribieron:
la calidad del reloj offline permanece explicita. Todos los MP4 siguen locales.

**Sincronizacion larga completada:** 164 objetos y 1986 registros confirmados,
sin pendientes de este recorrido. La consulta real de Render coincidio con el
informe local; se reprodujo un MP4 privado en el visor local.

### Reagrupacion del recorrido largo

Los originales se conservaron. Raspberry produjo seis MP4 sin recodificar:
cinco de 300 s y uno de 299.733 s, total 26 996 fotogramas. La nube conserva
ademas seis bloques finales con esos mismos conteos y un manifiesto de coleccion.
Cada bloque final se almacena en dos partes privadas por el limite individual
del plan Free; la pagina reconstruye un MP4 descargable. Esto duplica por ahora
el almacenamiento del recorrido: no se autorizaron eliminaciones de originales.

La grabacion directa de 300 s es un cambio posterior: no confundir la
reagrupacion verificada con un ensayo nuevo de captura directa ya completado.

Evidencia detallada con imagenes, coordenadas o tokens permanece fuera de Git.
Este documento contiene solo identificadores de ensayo y agregados tecnicos.
