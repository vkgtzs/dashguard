import 'package:material_ui/material_ui.dart';

import '../datos.dart';
import '../formato.dart';
import '../modelos.dart';
import '../tema.dart';
import 'comunes.dart';
import 'vehiculo.dart';

/// Lista de vehiculos con su estado y kilometraje
class PantallaVehiculos extends StatefulWidget {
  const PantallaVehiculos({super.key});

  @override
  State<PantallaVehiculos> createState() => _PantallaVehiculosState();
}

class _PantallaVehiculosState extends State<PantallaVehiculos> {
  late Future<List<Dispositivo>> _dispositivos = obtenerDispositivos();

  Future<void> _recargar() async {
    final nuevos = obtenerDispositivos();
    setState(() => _dispositivos = nuevos);
    try {
      await nuevos;
    } catch (_) {
      // el error se muestra en la lista
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<Dispositivo>>(
      future: _dispositivos,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return MensajeError(error: snapshot.error, alReintentar: _recargar);
        }
        if (!snapshot.hasData) {
          return const Center(child: CircularProgressIndicator());
        }
        final dispositivos = snapshot.data!;
        return RefreshIndicator(
          onRefresh: _recargar,
          child: dispositivos.isEmpty
              ? ListView(
                  children: const [
                    SizedBox(height: 120),
                    Center(child: Text('No tienes vehículos asignados')),
                  ],
                )
              : ListView.builder(
                  padding: const EdgeInsets.all(12),
                  itemCount: dispositivos.length,
                  itemBuilder: (context, i) {
                    final d = dispositivos[i];
                    return Card(
                      child: ListTile(
                        leading: CircleAvatar(
                          backgroundColor: d.enRecorrido ? verdeDashGuard : const Color(0xFFE9EDEA),
                          child: Icon(Icons.directions_car,
                              color: d.enRecorrido ? Colors.white : textoSecundario),
                        ),
                        title: Text(d.nombre),
                        subtitle: Text(
                          '${d.enRecorrido ? 'En recorrido' : 'Detenido'} · '
                          '${distancia(d.distanciaTotalM)} · límite ${d.limiteVelocidadKmh} km/h\n'
                          '${estadoConexion(d.vistoEn)}',
                        ),
                        isThreeLine: true,
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () async {
                          await Navigator.of(context).push(
                            MaterialPageRoute<void>(builder: (_) => PantallaVehiculo(dispositivo: d)),
                          );
                          _recargar();
                        },
                      ),
                    );
                  },
                ),
        );
      },
    );
  }
}
