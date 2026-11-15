import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart' show LatLng;
import 'package:material_ui/material_ui.dart';

import '../datos.dart';
import '../formato.dart';
import '../modelos.dart';

const saltoMaximo = Duration(seconds: 30);

const _colorRuta = Color(0xFF175FA6);
const _colorExceso = Color(0xFFE5484D);
const _colorInicio = Color(0xFF16834A);
const _colorFin = Color(0xFFC96816);

/// Divide los puntos en tramos continuos para dibujar una línea por tramo.
List<List<LatLng>> prepararTramos(List<Punto> puntos) {
  final tramos = <List<LatLng>>[];
  var tramo = <LatLng>[];
  DateTime? anterior;
  for (final p in puntos) {
    if (anterior != null) {
      final salto = p.fecha.difference(anterior);
      if (salto <= Duration.zero || salto > saltoMaximo) {
        if (tramo.isNotEmpty) tramos.add(tramo);
        tramo = <LatLng>[];
      }
    }
    tramo.add(LatLng(p.latitud, p.longitud));
    anterior = p.fecha;
  }
  if (tramo.isNotEmpty) tramos.add(tramo);
  return tramos;
}

/// Mapa con la ruta de una sesion: líinea del recorrido, inicio, fin y los puntos donde se supero el limite de velocidad
class PantallaMapaRecorrido extends StatefulWidget {
  const PantallaMapaRecorrido({
    super.key,
    required this.sesion,
    required this.nombreVehiculo,
    this.limiteKmh,
  });

  final Sesion sesion;
  final String nombreVehiculo;
  final int? limiteKmh;

  @override
  State<PantallaMapaRecorrido> createState() => _PantallaMapaRecorridoState();
}

class _PantallaMapaRecorridoState extends State<PantallaMapaRecorrido> {
  late final Future<List<Punto>> _puntos = obtenerPuntos(widget.sesion.id);

  /// Texto del punto que se toco en el mapa
  String? _seleccion;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.nombreVehiculo)),
      body: FutureBuilder<List<Punto>>(
        future: _puntos,
        builder: (context, snapshot) {
          if (snapshot.hasError) {
            return const Center(child: Text('No se pudo cargar el recorrido'));
          }
          if (!snapshot.hasData) {
            return const Center(child: CircularProgressIndicator());
          }
          final puntos = snapshot.data!;
          if (puntos.isEmpty) {
            return const Center(child: Text('Este recorrido no tiene puntos de GPS'));
          }
          return Column(
            children: [
              Expanded(child: _mapa(puntos)),
              _resumen(context),
            ],
          );
        },
      ),
    );
  }

  Widget _mapa(List<Punto> puntos) {
    final coordenadas = [for (final p in puntos) LatLng(p.latitud, p.longitud)];
    final limite = widget.limiteKmh;
    final excesos = limite == null
        ? const <Punto>[]
        : [for (final p in puntos) if ((p.velocidadKmh ?? 0) > limite) p];

    return FlutterMap(
      options: MapOptions(
        initialCenter: coordenadas.first,
        initialZoom: 16,
        initialCameraFit: coordenadas.length < 2
            ? null
            : CameraFit.bounds(
                bounds: LatLngBounds.fromPoints(coordenadas),
                padding: const EdgeInsets.all(25),
                maxZoom: 17,
              ),
      ),
      children: [
        TileLayer(
          urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
          userAgentPackageName: 'com.example.dashguard',
          maxZoom: 19,
        ),
        _CapaRuta(tramos: prepararTramos(puntos)),
        MarkerLayer(
          markers: [
            for (final p in excesos) _marcador(p, 'Exceso de velocidad', _colorExceso, 12),
            _marcador(puntos.first, 'Inicio', _colorInicio, 20),
            _marcador(puntos.last, 'Fin', _colorFin, 20),
          ],
        ),
        // Atribución obligatoria de OpenStreetMap
        Align(
          alignment: Alignment.bottomRight,
          child: Container(
            color: Colors.white.withValues(alpha: 0.8),
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            child: const Text(
              '© OpenStreetMap contributors',
              style: TextStyle(fontSize: 11, color: Colors.black87),
            ),
          ),
        ),
      ],
    );
  }

  /// Circulo que al tocarse muestra titulo, hora y velocidad del punto
  Marker _marcador(Punto p, String titulo, Color color, double diametro) {
    return Marker(
      point: LatLng(p.latitud, p.longitud),
      width: diametro + 12,
      height: diametro + 12,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: () => setState(() {
          _seleccion = '$titulo · ${hora(p.fecha)} · ${velocidad(p.velocidadKmh)}';
        }),
        child: Center(
          child: Container(
            width: diametro,
            height: diametro,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: color.withValues(alpha: 0.85),
              border: Border.all(color: Colors.white, width: 2),
            ),
          ),
        ),
      ),
    );
  }

  Widget _resumen(BuildContext context) {
    final s = widget.sesion;
    final tema = Theme.of(context);
    return Container(
      width: double.infinity,
      color: tema.colorScheme.surfaceContainerHighest,
      padding: const EdgeInsets.all(12),
      child: SafeArea(
        top: false,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(iconoVerificacion(s.verificacion), color: colorVerificacion(s.verificacion)),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    s.conductor ?? textoVerificacion(s.verificacion),
                    style: tema.textTheme.titleMedium,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text('${fechaHora(s.inicio)} · ${distancia(s.distanciaM)}'),
            const SizedBox(height: 4),
            Text(
              _seleccion ?? 'Toca un punto del mapa para ver la hora y la velocidad',
              style: tema.textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}

/// Dibuja la linea del recorrido sobre el mapa
class _CapaRuta extends StatelessWidget {
  const _CapaRuta({required this.tramos});

  final List<List<LatLng>> tramos;

  @override
  Widget build(BuildContext context) {
    // MapCamera.of hace que la capa se redibuje al mover o hacer zoom.
    final camara = MapCamera.of(context);
    return IgnorePointer(
      child: SizedBox.expand(
        child: CustomPaint(painter: _PintorRuta(camara: camara, tramos: tramos)),
      ),
    );
  }
}

class _PintorRuta extends CustomPainter {
  _PintorRuta({required this.camara, required this.tramos});

  final MapCamera camara;
  final List<List<LatLng>> tramos;

  @override
  void paint(Canvas canvas, Size size) {
    final pincel = Paint()
      ..color = _colorRuta.withValues(alpha: 0.7)
      ..strokeWidth = 4
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;

    for (final tramo in tramos) {
      if (tramo.length < 2) continue;
      final inicio = camara.latLngToScreenOffset(tramo.first);
      final trazo = Path()..moveTo(inicio.dx, inicio.dy);
      for (final punto in tramo.skip(1)) {
        final p = camara.latLngToScreenOffset(punto);
        trazo.lineTo(p.dx, p.dy);
      }
      canvas.drawPath(trazo, pincel);
    }
  }

  @override
  bool shouldRepaint(_PintorRuta anterior) =>
      anterior.camara != camara || anterior.tramos != tramos;
}
