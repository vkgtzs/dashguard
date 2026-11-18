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
/// El backend devuelve los ultimos 100 de todos los vehiculos y aqui se filtran
Future<List<Sesion>> obtenerSesiones(String dispositivoId) async {
  final json = await _llamar('GET', '/api/sesiones');
  return [
    for (final s in json['sesiones'] as List)
      if ((s as Map<String, dynamic>)['dispositivo_id'] == dispositivoId) Sesion.fromJson(s),
  ];
}

Future<List<Punto>> obtenerPuntos(String sesionId) async {
  final json = await _llamar('GET', '/api/sesiones/$sesionId');
  return [
    for (final p in json['puntos'] as List) Punto.fromJson(p as Map<String, dynamic>),
  ];
}

/// Alertas de un vehiculo, o de todos si no se indica, de la mas reciente a la mas antigua
/// El backend devuelve las ultimas 100 de todos los vehiculos y aqui se filtran
Future<List<Alerta>> obtenerAlertas([String? dispositivoId]) async {
  final json = await _llamar('GET', '/api/alertas');
  return [
    for (final a in json['alertas'] as List)
      if (dispositivoId == null || (a as Map<String, dynamic>)['dispositivo_id'] == dispositivoId)
        Alerta.fromJson(a as Map<String, dynamic>),
  ];
}

/// Nombre de cada vehiculo por su id, para mostrarlo en las listas generales
Future<Map<String, String>> nombresVehiculos() async =>
    {for (final d in await obtenerDispositivos()) d.id: d.nombre};

Future<void> marcarAlertaLeida(String alertaId) =>
    _llamar('PATCH', '/api/alertas/$alertaId', cuerpo: {'leida': true});

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

/// Una pagina de evidencias, de la mas reciente a la mas antigua
/// Sin dispositivoId trae las de todos los vehiculos; con antes, continua tras esa fecha
Future<({List<Evidencia> evidencias, bool hayMas})> obtenerEvidencias(
    {String? dispositivoId, DateTime? antes}) async {
  final consulta = {
    'dispositivo_id': ?dispositivoId,
    if (antes != null) 'antes': antes.toUtc().toIso8601String(),
  };
  final ruta = Uri(path: '/api/evidencias', queryParameters: consulta.isEmpty ? null : consulta);
  final json = await _llamar('GET', ruta.toString());
  final todas = json['evidencias'] as List;
  return (
    evidencias: [
      for (final e in todas)
        if (dispositivoId == null || (e as Map<String, dynamic>)['dispositivo_id'] == dispositivoId)
          Evidencia.fromJson(e as Map<String, dynamic>),
    ],
    hayMas: todas.length >= ((json['pagina'] as num?)?.toInt() ?? 50),
  );
}

/// Enlace temporal al archivo, vence en 5 minutos
Future<String> urlEvidencia(String evidenciaId) async {
  final json = await _llamar('GET', '/api/evidencias/$evidenciaId/url');
  return json['url'] as String;
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
    _ => http.get(url, headers: encabezados),
  };
  return enviar(peticion, 'el servidor de DashGuard');
}
