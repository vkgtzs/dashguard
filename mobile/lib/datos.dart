// Fuente de datos de la app: consulta el backend de DashGuard

import 'dart:convert';

import 'package:http/http.dart' as http;

import 'config.dart';
import 'modelos.dart';
import 'sesion.dart';

Future<List<Dispositivo>> obtenerDispositivos() async {
  final json = await _llamar('GET', '/api/dispositivos');
  return [
    for (final d in json['dispositivos'] as List) Dispositivo.fromJson(d as Map<String, dynamic>),
  ];
}

/// Recorridos de un vehiculo, del mas reciente al mas antiguo
Future<Pagina<Sesion>> obtenerSesiones(String dispositivoId, {DateTime? antes}) =>
    _pagina('/api/sesiones', 'sesiones', Sesion.fromJson,
        dispositivoId: dispositivoId, antes: antes);

Future<List<Punto>> obtenerPuntos(String sesionId) async {
  final json = await _llamar('GET', '/api/sesiones/$sesionId');
  return [
    for (final p in json['puntos'] as List) Punto.fromJson(p as Map<String, dynamic>),
  ];
}

/// Alertas de un vehiculo, o de todos si no se indica, de la mas reciente a la mas antigua
Future<Pagina<Alerta>> obtenerAlertas({String? dispositivoId, DateTime? antes}) =>
    _pagina('/api/alertas', 'alertas', Alerta.fromJson, dispositivoId: dispositivoId, antes: antes);

/// Cantidad de alertas sin leer de todos los vehiculos
Future<int> alertasPendientes() async {
  final json = await _llamar('GET', '/api/alertas/pendientes');
  return (json['pendientes'] as num).toInt();
}

/// Nombre de cada vehiculo por su id, para mostrarlo en las listas generales
Future<Map<String, String>> nombresVehiculos() async =>
    {for (final d in await obtenerDispositivos()) d.id: d.nombre};

Future<void> marcarAlertaLeida(String alertaId) =>
    _llamar('PATCH', '/api/alertas/$alertaId', cuerpo: {'leida': true});

/// Datos actualizados de un vehiculo (ubicacion, kilometraje, estado)
Future<Dispositivo> obtenerDispositivo(String dispositivoId) async {
  final dispositivos = await obtenerDispositivos();
  return dispositivos.firstWhere((d) => d.id == dispositivoId,
      orElse: () => throw const ErrorApp('Este vehículo ya no está en tu cuenta'));
}

Future<void> cambiarLimite(String dispositivoId, int limiteKmh) =>
    _llamar('PATCH', '/api/dispositivos/$dispositivoId', cuerpo: {'limite_velocidad_kmh': limiteKmh});

/// Pide al vehiculo una foto o un video corto
Future<Comando> solicitarCaptura(String dispositivoId, String tipo) async {
  final json = await _llamar('POST', '/api/comandos',
      cuerpo: {'dispositivo_id': dispositivoId, 'tipo': tipo});
  return Comando.fromJson(json['comando'] as Map<String, dynamic>);
}

/// Estado de una solicitud y, si ya se completo, su evidencia
Future<(Comando, Evidencia?)> consultarComando(String comandoId) async {
  final json = await _llamar('GET', '/api/comandos/$comandoId');
  final evidencia = json['evidencia'] as Map<String, dynamic>?;
  return (
    Comando.fromJson(json['comando'] as Map<String, dynamic>),
    evidencia == null ? null : Evidencia.fromJson(evidencia),
  );
}

/// Evidencias de un vehiculo, o de todos si no se indica, de la mas reciente a la mas antigua
Future<Pagina<Evidencia>> obtenerEvidencias({String? dispositivoId, DateTime? antes}) =>
    _pagina('/api/evidencias', 'evidencias', Evidencia.fromJson,
        dispositivoId: dispositivoId, antes: antes);

/// Enlace temporal al archivo, vence en 5 minutos
Future<String> urlEvidencia(String evidenciaId) async {
  final json = await _llamar('GET', '/api/evidencias/$evidenciaId/url');
  return json['url'] as String;
}

Future<List<Conductor>> obtenerConductores() async {
  final json = await _llamar('GET', '/api/conductores');
  return [
    for (final c in json['conductores'] as List) Conductor.fromJson(c as Map<String, dynamic>),
  ];
}

Future<Conductor> crearConductor(String nombre) async {
  final json = await _llamar('POST', '/api/conductores', cuerpo: {'nombre': nombre});
  return Conductor.fromJson(json['conductor'] as Map<String, dynamic>);
}

Future<Conductor> actualizarConductor(String conductorId,
    {String? nombre, bool? activo, bool borrarRostro = false}) async {
  final json = await _llamar('PATCH', '/api/conductores/$conductorId', cuerpo: {
    'nombre': ?nombre,
    'activo': ?activo,
    if (borrarRostro) 'borrar_rostro': true,
  });
  return Conductor.fromJson(json['conductor'] as Map<String, dynamic>);
}

Future<void> eliminarConductor(String conductorId) =>
    _llamar('DELETE', '/api/conductores/$conductorId');

/// Pide a un vehiculo que tome las muestras del rostro del conductor sentado frente a la camara
Future<Comando> solicitarRegistroRostro(String dispositivoId, String conductorId) async {
  final json = await _llamar('POST', '/api/comandos', cuerpo: {
    'dispositivo_id': dispositivoId,
    'tipo': 'registro_rostro',
    'conductor_id': conductorId,
  });
  return Comando.fromJson(json['comando'] as Map<String, dynamic>);
}

/// Pide una pagina al backend; antes indica desde donde continuar
Future<Pagina<T>> _pagina<T>(String ruta, String campo, T Function(Map<String, dynamic>) leer,
    {String? dispositivoId, DateTime? antes}) async {
  final consulta = {
    'dispositivo_id': ?dispositivoId,
    if (antes != null) 'antes': antes.toUtc().toIso8601String(),
  };
  final json = await _llamar(
      'GET', Uri(path: ruta, queryParameters: consulta.isEmpty ? null : consulta).toString());
  final filas = json[campo] as List;
  return (
    elementos: [for (final f in filas) leer(f as Map<String, dynamic>)],
    hayMas: filas.length >= ((json['pagina'] as num?)?.toInt() ?? 50),
  );
}

/// Llamada al backend con el token del supervisor, reintenta una vez si vencio
Future<Map<String, dynamic>> _llamar(String metodo, String ruta,
    {Map<String, dynamic>? cuerpo}) async {
  var r = await _pedir(metodo, ruta, cuerpo, await tokenVigente());
  if (r.statusCode == 401) r = await _pedir(metodo, ruta, cuerpo, await tokenVigente(forzar: true));
  final json = leerJson(r.body);
  if (r.statusCode == 401) throw const ErrorApp('Tu sesión venció, vuelve a iniciar sesión');
  if (r.statusCode < 200 || r.statusCode >= 300) {
    throw ErrorApp('${json['error'] ?? 'Error del servidor (código ${r.statusCode})'}');
  }
  return json;
}

Future<http.Response> _pedir(
    String metodo, String ruta, Map<String, dynamic>? cuerpo, String token) {
  final url = Uri.parse('$backendUrl$ruta');
  final encabezados = {'Authorization': 'Bearer $token'};
  final conCuerpo = {...encabezados, 'Content-Type': 'application/json'};
  final peticion = switch (metodo) {
    'POST' => http.post(url, headers: conCuerpo, body: jsonEncode(cuerpo)),
    'PATCH' => http.patch(url, headers: conCuerpo, body: jsonEncode(cuerpo)),
    'DELETE' => http.delete(url, headers: encabezados),
    _ => http.get(url, headers: encabezados),
  };
  return enviar(peticion, 'el servidor de DashGuard');
}
