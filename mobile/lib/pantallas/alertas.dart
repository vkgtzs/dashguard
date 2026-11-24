import 'package:material_ui/material_ui.dart';

import '../datos.dart';
import '../formato.dart';
import '../modelos.dart';
import 'comunes.dart';

/// Alertas de todos los vehiculos, al tocar una se marca como leida
class PantallaAlertas extends StatefulWidget {
  const PantallaAlertas({super.key, this.alLeer});

  /// Se llama al marcar una alerta como leida, para actualizar el contador
  final VoidCallback? alLeer;

  @override
  State<PantallaAlertas> createState() => _PantallaAlertasState();
}

class _PantallaAlertasState extends State<PantallaAlertas> {
  Map<String, String> _nombres = {};

  /// Alertas marcadas como leidas en esta pantalla
  final _leidas = <String>{};

  Future<Pagina<Alerta>> _cargar(DateTime? antes) async {
    if (antes == null) _nombres = await nombresVehiculos();
    return obtenerAlertas(antes: antes);
  }

  Future<void> _marcarLeida(Alerta a) async {
    setState(() => _leidas.add(a.id));
    try {
      await marcarAlertaLeida(a.id);
      widget.alLeer?.call();
    } catch (e) {
      if (!mounted) return;
      setState(() => _leidas.remove(a.id));
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListaPaginada<Alerta>(
      cargar: _cargar,
      fecha: (a) => a.fecha,
      vacio: 'No hay alertas',
      elemento: (context, a) {
        final leida = a.leida || _leidas.contains(a.id);
        final color = colorAlerta(a.tipo);
        return Card(
          child: ListTile(
            leading: Icon(iconoAlerta(a.tipo), color: color),
            title: Text(
              textoAlerta(a.tipo),
              style: TextStyle(fontWeight: leida ? FontWeight.normal : FontWeight.bold),
            ),
            subtitle: Text('${_nombres[a.dispositivoId] ?? a.dispositivoId}\n${_detalle(a)}'),
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
    );
  }

  String _detalle(Alerta a) {
    final kmh = a.detalle['velocidad_kmh'];
    if (a.tipo == 'exceso_velocidad' && kmh is num) {
      return '${fechaHora(a.fecha)} · ${velocidad(kmh.toDouble())}';
    }
    final porcentaje = a.detalle['porcentaje'];
    if (a.tipo == 'bateria_baja' && porcentaje is num) {
      return '${fechaHora(a.fecha)} · quedaba ${porcentaje.round()} %';
    }
    return fechaHora(a.fecha);
  }
}
