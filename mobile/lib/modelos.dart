// Modelos con los mismos campos que devuelve el backend (rutas /api).

class Dispositivo {
  const Dispositivo({
    required this.id,
    required this.nombre,
    required this.limiteVelocidadKmh,
    this.vistoEn,
  });

  final String id;
  final String nombre;
  final int limiteVelocidadKmh;
  final DateTime? vistoEn;

  factory Dispositivo.fromJson(Map<String, dynamic> j) => Dispositivo(
        id: j['id'] as String,
        nombre: j['nombre'] as String,
        limiteVelocidadKmh: (j['limite_velocidad_kmh'] as num).toInt(),
        vistoEn: _fecha(j['visto_en']),
      );
}

class Sesion {
  const Sesion({
    required this.id,
    required this.dispositivoId,
    required this.inicio,
    this.fin,
    this.verificacion,
    this.distanciaM,
    this.conductor,
  });

  final String id;
  final String dispositivoId;
  final DateTime inicio;
  final DateTime? fin;

  /// 'autorizado', 'no_reconocido', 'no_concluyente' o null si aún no hay resultado.
  final String? verificacion;
  final double? distanciaM;

  /// Nombre del conductor reconocido, si lo hubo.
  final String? conductor;

  factory Sesion.fromJson(Map<String, dynamic> j) => Sesion(
        id: j['id'] as String,
        dispositivoId: j['dispositivo_id'] as String,
        inicio: DateTime.parse(j['inicio'] as String),
        fin: _fecha(j['fin']),
        verificacion: j['verificacion'] as String?,
        distanciaM: (j['distancia_m'] as num?)?.toDouble(),
        conductor: (j['conductores'] as Map<String, dynamic>?)?['nombre'] as String?,
      );
}

class Punto {
  const Punto({
    required this.fecha,
    required this.latitud,
    required this.longitud,
    this.velocidadKmh,
  });

  final DateTime fecha;
  final double latitud;
  final double longitud;
  final double? velocidadKmh;

  factory Punto.fromJson(Map<String, dynamic> j) => Punto(
        fecha: DateTime.parse(j['fecha'] as String),
        latitud: (j['latitud'] as num).toDouble(),
        longitud: (j['longitud'] as num).toDouble(),
        velocidadKmh: (j['velocidad_kmh'] as num?)?.toDouble(),
      );
}

DateTime? _fecha(Object? valor) => valor == null ? null : DateTime.parse(valor as String);
