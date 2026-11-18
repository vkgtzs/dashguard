// Modelos con los mismos campos que devuelve el backend (rutas /api).

class Dispositivo {
  const Dispositivo({
    required this.id,
    required this.nombre,
    required this.limiteVelocidadKmh,
    this.vistoEn,
    this.ultimaPosicion,
    this.enRecorrido = false,
    this.recorridos = 0,
    this.distanciaTotalM = 0,
  });

  final String id;
  final String nombre;
  final int limiteVelocidadKmh;
  final DateTime? vistoEn;

  /// Ultimo punto de GPS recibido, o null si nunca ha enviado ubicacion
  final Punto? ultimaPosicion;

  /// true si su ultimo recorrido todavia no termina
  final bool enRecorrido;
  final int recorridos;

  /// Suma de la distancia de todos sus recorridos terminados
  final double distanciaTotalM;

  Dispositivo conLimite(int limite) => Dispositivo(
        id: id,
        nombre: nombre,
        limiteVelocidadKmh: limite,
        vistoEn: vistoEn,
        ultimaPosicion: ultimaPosicion,
        enRecorrido: enRecorrido,
        recorridos: recorridos,
        distanciaTotalM: distanciaTotalM,
      );

  factory Dispositivo.fromJson(Map<String, dynamic> j) => Dispositivo(
        id: j['id'] as String,
        nombre: j['nombre'] as String,
        limiteVelocidadKmh: (j['limite_velocidad_kmh'] as num).toInt(),
        vistoEn: _fecha(j['visto_en']),
        ultimaPosicion: j['ultima_posicion'] == null
            ? null
            : Punto.fromJson(j['ultima_posicion'] as Map<String, dynamic>),
        enRecorrido: j['en_recorrido'] as bool? ?? false,
        recorridos: (j['recorridos'] as num?)?.toInt() ?? 0,
        distanciaTotalM: (j['distancia_total_m'] as num?)?.toDouble() ?? 0,
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

  /// 'autorizado', 'no_reconocido', 'no_concluyente' o null si aun no hay resultado
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

class Alerta {
  const Alerta({
    required this.id,
    required this.dispositivoId,
    required this.tipo,
    required this.fecha,
    required this.leida,
    this.sesionId,
    this.latitud,
    this.longitud,
    this.detalle = const {},
  });

  final String id;
  final String dispositivoId;

  /// 'conductor_no_reconocido', 'verificacion_no_concluyente' o 'exceso_velocidad'
  final String tipo;
  final DateTime fecha;
  final bool leida;
  final String? sesionId;
  final double? latitud;
  final double? longitud;

  /// Datos extra que manda la Raspberry, por ejemplo la velocidad
  final Map<String, dynamic> detalle;

  factory Alerta.fromJson(Map<String, dynamic> j) => Alerta(
        id: j['id'] as String,
        dispositivoId: j['dispositivo_id'] as String,
        tipo: j['tipo'] as String,
        fecha: DateTime.parse(j['fecha'] as String),
        leida: j['leida'] as bool? ?? false,
        sesionId: j['sesion_id'] as String?,
        latitud: (j['latitud'] as num?)?.toDouble(),
        longitud: (j['longitud'] as num?)?.toDouble(),
        detalle: j['detalle'] as Map<String, dynamic>? ?? const {},
      );
}

class Comando {
  const Comando({required this.id, required this.tipo, required this.estado, this.error});

  final String id;

  /// 'foto', 'video' o 'registro_rostro'
  final String tipo;

  /// 'pendiente', 'completado', 'fallido' o 'expirado'
  final String estado;
  final String? error;

  factory Comando.fromJson(Map<String, dynamic> j) => Comando(
        id: j['id'] as String,
        tipo: j['tipo'] as String,
        estado: j['estado'] as String,
        error: j['error'] as String?,
      );
}

class Evidencia {
  const Evidencia({
    required this.id,
    required this.tipo,
    required this.fecha,
    this.dispositivoId,
    this.latitud,
    this.longitud,
    this.bytes,
  });

  final String id;

  /// 'foto' o 'video'
  final String tipo;
  final DateTime fecha;
  final String? dispositivoId;
  final double? latitud;
  final double? longitud;
  final int? bytes;

  factory Evidencia.fromJson(Map<String, dynamic> j) => Evidencia(
        id: j['id'] as String,
        tipo: j['tipo'] as String,
        fecha: DateTime.parse(j['fecha'] as String),
        dispositivoId: j['dispositivo_id'] as String?,
        latitud: (j['latitud'] as num?)?.toDouble(),
        longitud: (j['longitud'] as num?)?.toDouble(),
        bytes: (j['bytes'] as num?)?.toInt(),
      );
}

class Conductor {
  const Conductor({
    required this.id,
    required this.nombre,
    required this.activo,
    required this.rostroRegistrado,
    this.rostroActualizado,
  });

  final String id;
  final String nombre;

  /// Los conductores inactivos no se reconocen en ningun vehiculo
  final bool activo;
  final bool rostroRegistrado;
  final DateTime? rostroActualizado;

  factory Conductor.fromJson(Map<String, dynamic> j) => Conductor(
        id: j['id'] as String,
        nombre: j['nombre'] as String,
        activo: j['activo'] as bool? ?? true,
        rostroRegistrado: j['rostro_registrado'] as bool? ?? false,
        rostroActualizado: _fecha(j['rostro_actualizado']),
      );
}

/// Una pagina de una lista larga y si quedan mas elementos por pedir
typedef Pagina<T> = ({List<T> elementos, bool hayMas});
