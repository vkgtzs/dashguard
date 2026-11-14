// Fuente de datos de la app.
//
// Por ahora devuelve datos de prueba para poder avanzar en las pantallas sin
// depender del backend. Para conectar con la API real solo hay que cambiar el
// cuerpo de estas tres funciones (GET /api/dispositivos, /api/sesiones y
// /api/sesiones/:id) y usar los fromJson de modelos.dart.

import 'dart:math';

import 'modelos.dart';

Future<List<Dispositivo>> obtenerDispositivos() async => _dispositivos;

Future<List<Sesion>> obtenerSesiones() async => _sesiones;

Future<List<Punto>> obtenerPuntos(String sesionId) async {
  final sesion = _sesiones.firstWhere((s) => s.id == sesionId);
  return _puntosDePrueba(sesion.inicio, _sesiones.indexOf(sesion));
}

// ---------------------------------------------------------------------------
// Datos de prueba
// ---------------------------------------------------------------------------

final _ahora = DateTime.now();

final _dispositivos = [
  Dispositivo(
    id: 'dashguard-01',
    nombre: 'Nissan Versa',
    limiteVelocidadKmh: 80,
    vistoEn: _ahora.subtract(const Duration(minutes: 4)),
  ),
  Dispositivo(
    id: 'dashguard-02',
    nombre: 'Camioneta de reparto',
    limiteVelocidadKmh: 60,
    vistoEn: _ahora.subtract(const Duration(days: 2)),
  ),
];

final _sesiones = [
  Sesion(
    id: '00000000-0000-4000-8000-000000000001',
    dispositivoId: 'dashguard-01',
    inicio: _ahora.subtract(const Duration(hours: 1)),
    fin: _ahora.subtract(const Duration(minutes: 45)),
    verificacion: 'autorizado',
    distanciaM: 9800,
    conductor: 'Conductor de prueba',
  ),
  Sesion(
    id: '00000000-0000-4000-8000-000000000002',
    dispositivoId: 'dashguard-01',
    inicio: _ahora.subtract(const Duration(hours: 26)),
    fin: _ahora.subtract(const Duration(hours: 25, minutes: 40)),
    verificacion: 'no_reconocido',
    distanciaM: 12400,
  ),
  Sesion(
    id: '00000000-0000-4000-8000-000000000003',
    dispositivoId: 'dashguard-02',
    inicio: _ahora.subtract(const Duration(days: 2, hours: 3)),
    fin: _ahora.subtract(const Duration(days: 2, hours: 2, minutes: 48)),
    verificacion: 'no_concluyente',
    distanciaM: 7300,
  ),
];

/// Genera un recorrido ficticio en Tijuana: un punto cada 5 s, con un hueco de
/// GPS a la mitad y tramos por encima del límite de velocidad.
List<Punto> _puntosDePrueba(DateTime inicio, int variante) {
  final puntos = <Punto>[];
  var latitud = 32.5310 + variante * 0.004;
  var longitud = -116.9650;
  var fecha = inicio;
  for (var i = 0; i < 150; i++) {
    fecha = fecha.add(Duration(seconds: i == 75 ? 60 : 5));
    latitud += 0.00035 * cos(i / 40 + variante);
    longitud -= 0.00045 * (0.6 + 0.4 * sin(i / 25));
    puntos.add(Punto(
      fecha: fecha,
      latitud: latitud,
      longitud: longitud,
      velocidadKmh: 45 + 45 * sin(i / 12).abs(),
    ));
  }
  return puntos;
}
