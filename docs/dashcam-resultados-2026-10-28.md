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

Python en Windows: 26 pruebas antes de agregar el caso de recuperacion; cinco
pruebas nuevas de cola/recuperacion pasaron en Raspberry, ademas de pruebas IMU y
grabador previas (11 en primer pase). Node: nueve pruebas aprobadas.
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

## Ensayo de 30 minutos con powerbank: en curso

El usuario confirmo INIU BI-B41, USB-A a PWR IN, cable marcado 2.1 A.
Confirmo arranque con esa powerbank aproximadamente a las 08:27 de Tijuana.
Wi-Fi de Raspberry se apago antes del apagado controlado; se instalo reconexion
automatica a los 33 min del proximo arranque. PC mantiene Internet.

**Pendiente de leer al reconectar**: boot_id nuevo, arranque sin NTP/RTC,
30 minutos de captura, integridad/continuidad de segmentos, temperatura,
throttling, ausencia de Internet durante captura, cierre, sincronizacion completa
y consulta del recorrido largo. No declarar listo para uso en carro antes de ello.

Evidencia detallada con imagenes, coordenadas o tokens permanece fuera de Git.
Este documento contiene solo identificadores de ensayo y agregados tecnicos.
