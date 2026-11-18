import 'package:material_ui/material_ui.dart';

import '../datos.dart';
import '../formato.dart';
import '../modelos.dart';
import 'comunes.dart';

/// Alertas de todos los vehiculos, al tocar una se marca como leida
class PantallaAlertas extends StatefulWidget {
  const PantallaAlertas({super.key});

  @override
  State<PantallaAlertas> createState() => _PantallaAlertasState();
}

class _PantallaAlertasState extends State<PantallaAlertas> {
  late Future<(List<Alerta>, Map<String, String>)> _datos = _cargar();

  /// Alertas marcadas como leidas en esta pantalla
  final _leidas = <String>{};

  Future<(List<Alerta>, Map<String, String>)> _cargar() async {
    final nombres = await nombresVehiculos();
    return (await obtenerAlertas(), nombres);
  }

  Future<void> _recargar() async {
    final nuevos = _cargar();
    setState(() => _datos = nuevos);
    try {
      await nuevos;
    } catch (_) {
      // el error se muestra en la lista
    }
  }

  Future<void> _marcarLeida(Alerta a) async {
    setState(() => _leidas.add(a.id));
    try {
      await marcarAlertaLeida(a.id);
    } catch (e) {
      if (!mounted) return;
      setState(() => _leidas.remove(a.id));
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<(List<Alerta>, Map<String, String>)>(
      future: _datos,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return MensajeError(error: snapshot.error, alReintentar: _recargar);
        }
        if (!snapshot.hasData) {
          return const Center(child: CircularProgressIndicator());
        }
        final (alertas, nombres) = snapshot.data!;
        return RefreshIndicator(
          onRefresh: _recargar,
          child: alertas.isEmpty
              ? ListView(
                  children: const [
                    SizedBox(height: 120),
                    Center(child: Text('No hay alertas')),
                  ],
                )
              : ListView.builder(
                  padding: const EdgeInsets.all(12),
                  itemCount: alertas.length,
                  itemBuilder: (context, i) {
                    final a = alertas[i];
                    final leida = a.leida || _leidas.contains(a.id);
                    final color = colorAlerta(a.tipo);
                    return Card(
                      child: ListTile(
                        leading: Icon(iconoAlerta(a.tipo), color: color),
                        title: Text(
                          textoAlerta(a.tipo),
                          style: TextStyle(fontWeight: leida ? FontWeight.normal : FontWeight.bold),
                        ),
                        subtitle: Text('${nombres[a.dispositivoId] ?? a.dispositivoId}\n'
                            '${_detalle(a)}'),
                        isThreeLine: true,
                        trailing: leida
                            ? null
                            : Container(
                                width: 10,
                                height: 10,
                                decoration: BoxDecoration(shape: BoxShape.circle, color: color),
                              ),
                        onTap: leida ? null : () => _marcarLeida(a),
                      ),
                    );
                  },
                ),
        );
      },
    );
  }

  String _detalle(Alerta a) {
    final kmh = a.detalle['velocidad_kmh'];
    if (a.tipo == 'exceso_velocidad' && kmh is num) {
      return '${fechaHora(a.fecha)} · ${velocidad(kmh.toDouble())}';
    }
    return fechaHora(a.fecha);
  }
}
