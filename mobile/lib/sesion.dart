// Inicio de sesion del supervisor con Supabase Auth
// La sesion vive en memoria: al cerrar la app hay que volver a entrar

import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import 'config.dart';

/// Render gratuito puede tardar casi un minuto en despertar
const tiempoMaximo = Duration(seconds: 90);

/// Error con un mensaje listo para mostrar en pantalla
class ErrorApp implements Exception {
  const ErrorApp(this.mensaje, {this.rechazado = false});

  final String mensaje;

  /// true cuando el servidor respondio que no (no fue falla de red)
  final bool rechazado;

  @override
  String toString() => mensaje;
}

const _sesionVencida = ErrorApp('Tu sesión venció, vuelve a iniciar sesión');

String? _accessToken;
String? _refreshToken;
DateTime? _expira;
Future<void>? _renovando;

Future<void> iniciarSesion(String correo, String contrasena) =>
    _pedirToken('password', {'email': correo.trim(), 'password': contrasena});

void cerrarSesion() {
  _accessToken = null;
  _refreshToken = null;
  _expira = null;
}

/// Token para llamar al backend, se renueva si esta por vencer o si se fuerza
Future<String> tokenVigente({bool forzar = false}) async {
  if (_accessToken == null) throw _sesionVencida;
  final porVencer = _expira == null ||
      DateTime.now().isAfter(_expira!.subtract(const Duration(minutes: 1)));
  if (forzar || porVencer) {
    _renovando ??= _renovar().whenComplete(() => _renovando = null);
    await _renovando;
  }
  return _accessToken!;
}

Future<void> _renovar() async {
  final refresh = _refreshToken;
  if (refresh == null) throw _sesionVencida;
  try {
    await _pedirToken('refresh_token', {'refresh_token': refresh});
  } on ErrorApp catch (e) {
    if (!e.rechazado) rethrow;
    cerrarSesion();
    throw _sesionVencida;
  }
}

Future<void> _pedirToken(String tipo, Map<String, String> cuerpo) async {
  final r = await enviar(
    http.post(
      Uri.parse('$supabaseUrl/auth/v1/token?grant_type=$tipo'),
      headers: {'apikey': supabaseClavePublica, 'Content-Type': 'application/json'},
      body: jsonEncode(cuerpo),
    ),
    'el servidor de inicio de sesión',
  );
  final json = leerJson(r.body);
  if (r.statusCode != 200) {
    final codigo = '${json['error_code'] ?? json['error'] ?? ''}';
    throw ErrorApp(
      switch (codigo) {
        'invalid_credentials' || 'invalid_grant' => 'Correo o contraseña incorrectos',
        'email_not_confirmed' => 'El correo todavía no está confirmado en Supabase',
        _ => 'No se pudo iniciar sesión (código ${r.statusCode})',
      },
      rechazado: r.statusCode < 500,
    );
  }
  _accessToken = json['access_token'] as String;
  _refreshToken = json['refresh_token'] as String;
  _expira = DateTime.now().add(Duration(seconds: (json['expires_in'] as num).toInt()));
}

/// Espera la respuesta y convierte fallas de red en mensajes legibles
Future<http.Response> enviar(Future<http.Response> peticion, String quien) async {
  try {
    return await peticion.timeout(tiempoMaximo);
  } on TimeoutException {
    throw ErrorApp('No hubo respuesta a tiempo de $quien, intenta de nuevo');
  } on http.ClientException {
    throw ErrorApp('No hay conexión con $quien, revisa tu internet');
  }
}

Map<String, dynamic> leerJson(String texto) {
  try {
    final valor = jsonDecode(texto);
    return valor is Map<String, dynamic> ? valor : {};
  } on FormatException {
    return {};
  }
}
