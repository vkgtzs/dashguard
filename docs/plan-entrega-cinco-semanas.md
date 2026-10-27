# Entrega DashGuard: cinco semanas

Plan relativo, ajustable tras medir Zero 2 W. Cada semana cierra con una
demostracion reproducible y evidencia, no solo modulos aislados.

| Semana | Entregable demostrable | Condicion de cierre |
|---|---|---|
| 1 | Grabacion y deteccion desde una camara; decision de identificador | Medir base/deteccion, cadencia, CPU, RAM, temperatura; conservar video y resultados; seleccionar alternativa viable |
| 2 | Enrolamiento local, comparacion y evento con clip protegido | Probar autorizado, persona distinta y resultado incierto; sin afirmar prueba de vida |
| 3 | Recorrido offline y consulta web real | Inicio/fin persistentes, sincronizacion idempotente, eventos visibles, autenticacion minima y backend comprobado |
| 4 | Conjunto estable y reporte por recorrido | Ensayo prolongado, Wi-Fi desconectado/reconectado, almacenamiento global y apagado controlado |
| 5 | Version congelada, instalacion y defensa | Guion de demostracion, resultados con limites, recuperacion y documentacion reproducible |

Obligatorio: identificar propietario/persona autorizada bajo condiciones de
demostracion definidas; incertidumbre explicita; eventos y evidencia local;
GPS/IMU, segmentos y proteccion; recorridos offline y sincronizacion posterior;
consulta web y reporte basico. Identificar no equivale a demostrar presencia
de una persona viva: una fotografia puede enganar un sistema sin anti-suplantacion.

Deseable: mejor interfaz, mas condiciones de iluminacion, acelerador Coral solo
si mediciones y compatibilidad justifican su costo de integracion, UPS/RTC
solo tras seleccionar hardware compatible.

Fuera de alcance: placas, iluminacion automatica, conectividad celular integrada,
garantia de deteccion de incidentes, precision temporal fisica por fotograma y
prueba de vida certificada. No alimentar Raspberry directamente con la LiPo.

## Decision de identificacion tras deteccion

Primero comprobar frontalidad/tamano y frecuencia util con grabacion. Propuesta
de criterio inicial de ingenieria (no requisito academico): >=1 analisis/s,
p95 de analisis <500 ms, video cercano a 15 fps sin regresion clara contra base,
sin throttling y margen de memoria. Son umbrales de ensayo, no resultados.

Si se cumple: evaluar un identificador ligero sobre recortes de rostro, a baja
frecuencia, en esta misma sesion; comparar embeddings o LBPH como candidatos
medidos, sin escoger solo por fama. Separar desarrollo y evaluacion, incorporar
personas no enroladas y calibrar umbral de rechazo. No confundir puntuacion con
probabilidad de identidad. Una sola persona enrolada no prueba generalizacion.

Resultados futuros: autorizado solo con evidencia repetida y umbral validado;
desconocido solo con rostro util y comparacion suficiente; incierto para ausencia,
poca luz, rostro pequeno/oculto, varios rostros o comparacion ambigua. Umbrales y
ventana temporal se fijaran con datos de evaluacion. No disparar evento de intruso
por ausencia de rostro. Si el rendimiento falla, reducir frecuencia/resolucion o
cambiar detector antes de evaluar Coral (modelo, interfaz y compatibilidad 32 bits).
