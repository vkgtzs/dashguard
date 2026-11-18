import 'package:material_ui/material_ui.dart';

import '../datos.dart';
import '../formato.dart';
import '../modelos.dart';
import 'comunes.dart';
import 'vehiculo.dart';

/// Lista de vehiculos 
class PantallaVehiculos extends StatefulWidget {
  const PantallaVehiculos({super.key});

  @override
  State<PantallaVehiculos> createState() => _PantallaVehiculosState();
}

class _PantallaVehiculosState extends State<PantallaVehiculos> {
  late Future<List<Dispositivo>> _dispositivos = obtenerDispositivos();

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<Dispositivo>>(
      future: _dispositivos,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return MensajeError(
            error: snapshot.error,
            alReintentar: () => setState(() => _dispositivos = obtenerDispositivos()),
          );
        }
        if (!snapshot.hasData) {
          return const Center(child: CircularProgressIndicator());
        }
        final dispositivos = snapshot.data!;
        if (dispositivos.isEmpty) {
          return const Center(child: Text('No tienes vehículos asignados'));
        }
        return ListView.builder(
          padding: const EdgeInsets.all(12),
          itemCount: dispositivos.length,
          itemBuilder: (context, i) {
            final d = dispositivos[i];
            return Card(
              child: ListTile(
                leading: const Icon(Icons.directions_car),
                title: Text(d.nombre),
                subtitle: Text(
                  'Límite: ${d.limiteVelocidadKmh} km/h\n'
                  'Última conexión: ${haceCuanto(d.vistoEn)}',
                ),
                isThreeLine: true,
                trailing: const Icon(Icons.chevron_right),
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(builder: (_) => PantallaVehiculo(dispositivo: d)),
                ),
              ),
            );
          },
        );
      },
    );
  }
}
