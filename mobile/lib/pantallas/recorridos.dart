import 'package:material_ui/material_ui.dart';

import '../datos.dart';
import '../formato.dart';
import '../modelos.dart';
import 'comunes.dart';
import 'mapa_recorrido.dart';

/// Lista de recorridos de un vehiculo
class PantallaRecorridos extends StatefulWidget {
  const PantallaRecorridos({super.key, required this.dispositivo});

  final Dispositivo dispositivo;

  @override
  State<PantallaRecorridos> createState() => _PantallaRecorridosState();
}

class _PantallaRecorridosState extends State<PantallaRecorridos> {
  late Future<List<Sesion>> _sesiones = obtenerSesiones(widget.dispositivo.id);

  @override
  Widget build(BuildContext context) {
    final d = widget.dispositivo;
    return FutureBuilder<List<Sesion>>(
      future: _sesiones,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return MensajeError(
            error: snapshot.error,
            alReintentar: () => setState(() => _sesiones = obtenerSesiones(d.id)),
          );
        }
        if (!snapshot.hasData) {
          return const Center(child: CircularProgressIndicator());
        }
        final sesiones = snapshot.data!;
        if (sesiones.isEmpty) {
          return const Center(child: Text('Este vehículo todavía no tiene recorridos'));
        }
        return ListView.builder(
          padding: const EdgeInsets.all(12),
          itemCount: sesiones.length,
          itemBuilder: (context, i) {
            final s = sesiones[i];
            return Card(
              child: ListTile(
                leading: Icon(
                  iconoVerificacion(s.verificacion),
                  color: colorVerificacion(s.verificacion),
                ),
                title: Text(fechaHora(s.inicio)),
                subtitle: Text(
                  '${s.conductor ?? textoVerificacion(s.verificacion)}\n'
                  '${distancia(s.distanciaM)}${s.fin == null ? ' · en curso' : ''}',
                ),
                isThreeLine: true,
                trailing: const Icon(Icons.chevron_right),
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => PantallaMapaRecorrido(
                      sesion: s,
                      nombreVehiculo: d.nombre,
                      limiteKmh: d.limiteVelocidadKmh,
                    ),
                  ),
                ),
              ),
            );
          },
        );
      },
    );
  }
}
