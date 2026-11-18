import 'package:material_ui/material_ui.dart';

import '../modelos.dart';
import 'captura.dart';
import 'evidencias.dart';
import 'recorridos.dart';

/// Detalle de un vehiculo con sus recorridos, sus evidencias y el boton de captura
class PantallaVehiculo extends StatefulWidget {
  const PantallaVehiculo({super.key, required this.dispositivo});

  final Dispositivo dispositivo;

  @override
  State<PantallaVehiculo> createState() => _PantallaVehiculoState();
}

class _PantallaVehiculoState extends State<PantallaVehiculo> {
  /// Cambia despues de cada captura para que la lista de evidencias se vuelva a consultar
  int _recarga = 0;

  Future<void> _capturar() async {
    await elegirCaptura(context, widget.dispositivo);
    if (mounted) setState(() => _recarga++);
  }

  @override
  Widget build(BuildContext context) {
    final d = widget.dispositivo;
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: Text(d.nombre),
          bottom: const TabBar(
            tabs: [
              Tab(icon: Icon(Icons.route_outlined), text: 'Recorridos'),
              Tab(icon: Icon(Icons.photo_camera_outlined), text: 'Evidencias'),
            ],
          ),
        ),
        floatingActionButton: FloatingActionButton.extended(
          onPressed: _capturar,
          icon: const Icon(Icons.photo_camera),
          label: const Text('Capturar'),
        ),
        body: TabBarView(
          children: [
            PantallaRecorridos(dispositivo: d),
            PantallaEvidencias(key: ValueKey(_recarga), dispositivo: d),
          ],
        ),
      ),
    );
  }
}
