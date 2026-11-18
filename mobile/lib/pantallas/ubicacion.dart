import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart' show LatLng;
import 'package:material_ui/material_ui.dart';

import '../datos.dart';
import '../formato.dart';
import '../modelos.dart';
import 'comunes.dart';

/// Ultima ubicacion conocida del vehiculo, su estado y su kilometraje
class PantallaUbicacion extends StatefulWidget {
  const PantallaUbicacion({super.key, required this.dispositivo});

  final Dispositivo dispositivo;

  @override
  State<PantallaUbicacion> createState() => _PantallaUbicacionState();
}

class _PantallaUbicacionState extends State<PantallaUbicacion> {
  late Future<Dispositivo> _datos = obtenerDispositivo(widget.dispositivo.id);

  void _recargar() => setState(() => _datos = obtenerDispositivo(widget.dispositivo.id));

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Dispositivo>(
      future: _datos,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return MensajeError(error: snapshot.error, alReintentar: _recargar);
        }
        if (!snapshot.hasData) {
          return const Center(child: CircularProgressIndicator());
        }
        final d = snapshot.data!;
        final p = d.ultimaPosicion;
        final esquema = Theme.of(context).colorScheme;
        return Column(
          children: [
            Card(
              margin: const EdgeInsets.all(12),
              child: Column(
                children: [
                  ListTile(
                    leading: Icon(
                      d.enRecorrido ? Icons.route : Icons.local_parking,
                      color: d.enRecorrido ? const Color(0xFF16834A) : esquema.outline,
                    ),
                    title: Text(d.enRecorrido ? 'En recorrido' : 'Detenido'),
                    subtitle: Text(p == null
                        ? 'Sin ubicación registrada'
                        : 'Última ubicación ${haceCuanto(p.fecha)} · ${velocidad(p.velocidadKmh)}'),
                    trailing: IconButton(
                      tooltip: 'Actualizar',
                      icon: const Icon(Icons.refresh),
                      onPressed: _recargar,
                    ),
                  ),
                  ListTile(
                    leading: const Icon(Icons.speed),
                    title: Text('${distancia(d.distanciaTotalM)} recorridos en total'),
                    subtitle: Text('${d.recorridos} recorridos · '
                        'límite ${d.limiteVelocidadKmh} km/h'),
                  ),
                ],
              ),
            ),
            Expanded(
              child: p == null
                  ? const Center(child: Text('Este vehículo todavía no ha enviado su ubicación'))
                  : FlutterMap(
                      options: MapOptions(
                        initialCenter: LatLng(p.latitud, p.longitud),
                        initialZoom: 16,
                      ),
                      children: [
                        TileLayer(
                          urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                          userAgentPackageName: 'com.example.dashguard',
                          maxZoom: 19,
                        ),
                        MarkerLayer(
                          markers: [
                            Marker(
                              point: LatLng(p.latitud, p.longitud),
                              width: 44,
                              height: 44,
                              child: Icon(Icons.directions_car_filled, size: 36, color: esquema.primary),
                            ),
                          ],
                        ),
                      ],
                    ),
            ),
          ],
        );
      },
    );
  }
}
