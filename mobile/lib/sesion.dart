// Cuenta del supervisor con Supabase Auth: iniciar sesion, crear cuenta, verificar el
// correo con un codigo, recuperar la contrasena y mantener la sesion iniciada.
// El token para renovar la sesion se guarda cifrado en el telefono.

import 'dart:async';
import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

import 'config.dart';

/// Render gratuito puede tardar casi un minuto en despertar
const tiempoMaximo = Duration(seconds: 90);

/// Error con un mensaje listo para mostrar en pantalla
class ErrorApp implements Exception {
  const ErrorApp(this.mensaje, {this.rechazado = false, this.codigo});

  final String mensaje;

  /// true cuando el servidor respondio que no (no fue falla de red)
  final bool rechazado;

  /// Codigo de error de Supabase, por ejemplo 'email_not_confirmed'
  final String? codigo;

  @override
  String toString() => mensaje;
}

const _sesionVencida = ErrorApp('Tu sesión venció, vuelve a iniciar sesión');
const _almacen = FlutterSecureStorage();
const _claveRenovacion = 'dashguard_refresh_token';

String? _accessToken;
String? _refreshToken;
DateTime? _expira;
Future<void>? _renovando;

Map<String, String> get _cabeceras =>
    {'apikey': supabaseClavePublica, 'Content-Type': 'application/json'};

Uri _ruta(String ruta) => Uri.parse('$supabaseUrl/auth/v1/$ruta');

Future<void> iniciarSesion(String correo, String contrasena) =>
    _pedirToken('password', {'email': correo.trim(), 'password': contrasena});

/// Al abrir la app: recupera la sesion guardada. Devuelve false si no hay o ya no sirve.
/// Si no hay conexion lanza ErrorApp y conserva la sesion guardada para reintentar.
Future<bool> restaurarSesion() async {
  final String? guardado;
  try {
    guardado = await _almacen.read(key: _claveRenovacion);
  } catch (_) {
    return false;
  }
  if (guardado == null) return false;
  try {
    await _pedirToken('refresh_token', {'refresh_token': guardado});
    return true;
  } on ErrorApp catch (e) {
    if (!e.rechazado) rethrow;
    await _olvidarSesion();
    return false;
  }
}

Future<void> cerrarSesion() async {
  final token = _accessToken;
  await _olvidarSesion();
  if (token == null) return;
  try {
    // invalida la sesion en el servidor; si no hay conexion basta con olvidarla aqui
    await http
        .post(_ruta('logout'), headers: {..._cabeceras, 'Authorization': 'Bearer $token'})
        .timeout(const Duration(seconds: 10));
  } catch (_) {}
}

Future<void> _olvidarSesion() async {
  _accessToken = null;
  _refreshToken = null;
  _expira = null;
  try {
    await _almacen.delete(key: _claveRenovacion);
  } catch (_) {}
}

/// Crea la cuenta. Devuelve true si ya quedo con la sesion iniciada; false si hay que
/// confirmar el correo con el codigo que envia Supabase.
Future<bool> crearCuenta(String nombre, String correo, String contrasena) async {
  final json = await _llamarCuenta('POST', 'signup', {
    'email': correo.trim(),
    'password': contrasena,
    'data': {'nombre': nombre.trim()},
  });
  if (json['access_token'] != null) {
    await _guardarSesion(json);
    return true;
  }
  // Supabase responde igual si el correo ya tiene cuenta, para no revelarlo; la unica
  // diferencia es que esa respuesta no trae identidades
  final identidades = json['identities'] as List?;
  if (identidades != null && identidades.isEmpty) {
    throw const ErrorApp('Ya existe una cuenta con ese correo. Inicia sesión o recupera tu contraseña.',
        rechazado: true, codigo: 'user_already_exists');
  }
  return false;
}

/// Confirma el correo (tipo 'signup') o una recuperacion de contrasena (tipo 'recovery')
/// con el codigo que llego por correo. Deja la sesion iniciada.
Future<void> verificarCodigo(String correo, String codigo, String tipo) async {
  final json = await _llamarCuenta('POST', 'verify', {
    'type': tipo,
    'email': correo.trim(),
    'token': codigo.trim(),
  });
  await _guardarSesion(json);
}

Future<void> reenviarCodigoRegistro(String correo) =>
    _llamarCuenta('POST', 'resend', {'type': 'signup', 'email': correo.trim()});

Future<void> solicitarRecuperacion(String correo) =>
    _llamarCuenta('POST', 'recover', {'email': correo.trim()});

/// Cambia la contrasena de la sesion actual (despues de verificar el codigo de recuperacion)
Future<void> cambiarContrasena(String nueva) async {
  final token = await tokenVigente();
  await _llamarCuenta('PUT', 'user', {'password': nueva}, token: token);
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
    await _olvidarSesion();
    throw _sesionVencida;
  }
}

Future<void> _pedirToken(String tipo, Map<String, String> cuerpo) async {
  final r = await enviar(
    http.post(_ruta('token?grant_type=$tipo'), headers: _cabeceras, body: jsonEncode(cuerpo)),
    'el servidor de inicio de sesión',
  );
  final json = leerJson(r.body);
  if (r.statusCode != 200) throw _errorCuenta(r.statusCode, json);
  await _guardarSesion(json);
}

Future<Map<String, dynamic>> _llamarCuenta(String metodo, String ruta, Map<String, dynamic> cuerpo,
    {String? token}) async {
  final cabeceras = {..._cabeceras, 'Authorization': 'Bearer ${token ?? supabaseClavePublica}'};
  final peticion = metodo == 'PUT'
      ? http.put(_ruta(ruta), headers: cabeceras, body: jsonEncode(cuerpo))
      : http.post(_ruta(ruta), headers: cabeceras, body: jsonEncode(cuerpo));
  final r = await enviar(peticion, 'el servidor de cuentas');
  final json = leerJson(r.body);
  if (r.statusCode < 200 || r.statusCode >= 300) throw _errorCuenta(r.statusCode, json);
  return json;
}

Future<void> _guardarSesion(Map<String, dynamic> json) async {
  _accessToken = json['access_token'] as String;
  _refreshToken = json['refresh_token'] as String;
  _expira = DateTime.now().add(Duration(seconds: (json['expires_in'] as num).toInt()));
  try {
    await _almacen.write(key: _claveRenovacion, value: _refreshToken);
  } catch (_) {
    // si el telefono no deja guardarla, la sesion sigue funcionando hasta cerrar la app
  }
}

ErrorApp _errorCuenta(int estado, Map<String, dynamic> json) {
  final codigo = '${json['error_code'] ?? json['error'] ?? ''}';
  final mensaje = switch (codigo) {
    'invalid_credentials' || 'invalid_grant' => 'Correo o contraseña incorrectos',
    'email_not_confirmed' => 'Tu correo todavía no está confirmado',
    'user_already_exists' || 'email_exists' =>
      'Ya existe una cuenta con ese correo. Inicia sesión o recupera tu contraseña.',
    'weak_password' => 'La contraseña es muy débil; usa al menos 8 caracteres con letras y números',
    'same_password' => 'La nueva contraseña debe ser distinta a la anterior',
    'email_address_invalid' || 'validation_failed' => 'Revisa que el correo esté bien escrito',
    'otp_expired' => 'El código es incorrecto o ya venció; pide uno nuevo',
    'over_email_send_rate_limit' =>
      'Se enviaron demasiados correos; espera unos minutos e intenta de nuevo',
    'over_request_rate_limit' => 'Demasiados intentos; espera un momento',
    'signup_disabled' => 'El registro de cuentas está desactivado',
    _ => 'No se pudo completar la operación (código $estado)',
  };
  return ErrorApp(mensaje, rechazado: estado < 500, codigo: codigo);
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
