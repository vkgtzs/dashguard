// Funciones para mostrar fechas, distancias y resultados de verificacion

import 'package:material_ui/material_ui.dart';

String _dos(int n) => n.toString().padLeft(2, '0');

/// 14/11/2026 08:05
String fechaHora(DateTime fecha) {
  final f = fecha.toLocal();
  return '${_dos(f.day)}/${_dos(f.month)}/${f.year} ${_dos(f.hour)}:${_dos(f.minute)}';
}

/// 08:05:30
String hora(DateTime fecha) {
  final f = fecha.toLocal();
  return '${_dos(f.hour)}:${_dos(f.minute)}:${_dos(f.second)}';
}

String distancia(double? metros) {
  if (metros == null) return 'distancia no disponible';
  return metros < 1000 ? '${metros.round()} m' : '${(metros / 1000).toStringAsFixed(1)} km';
}

String velocidad(double? kmh) => kmh == null ? 'velocidad no disponible' : '${kmh.round()} km/h';

String haceCuanto(DateTime? fecha) {
  if (fecha == null) return 'nunca se ha conectado';
  final d = DateTime.now().difference(fecha);
  if (d.inMinutes < 1) return 'hace un momento';
  if (d.inMinutes < 60) return 'hace ${d.inMinutes} min';
  if (d.inHours < 24) return 'hace ${d.inHours} h';
  return 'hace ${d.inDays} d';
}

String textoVerificacion(String? verificacion) => switch (verificacion) {
      'autorizado' => 'Conductor autorizado',
      'no_reconocido' => 'Conductor no reconocido',
      'no_concluyente' => 'Verificación no concluyente',
      _ => 'Sin verificación',
    };

IconData iconoVerificacion(String? verificacion) => switch (verificacion) {
      'autorizado' => Icons.verified_user_outlined,
      'no_reconocido' => Icons.gpp_bad_outlined,
      'no_concluyente' => Icons.gpp_maybe_outlined,
      _ => Icons.help_outline,
    };

Color colorVerificacion(String? verificacion) => switch (verificacion) {
      'autorizado' => const Color(0xFF16834A),
      'no_reconocido' => const Color(0xFFB3261E),
      'no_concluyente' => const Color(0xFFC96816),
      _ => const Color(0xFF757575),
    };
