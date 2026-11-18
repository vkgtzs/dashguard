import 'package:material_ui/material_ui.dart';

import '../datos.dart';
import '../modelos.dart';
import 'captura.dart';
import 'comunes.dart';
import 'evidencias.dart';
import 'recorridos.dart';
import 'ubicacion.dart';

/// Detalle de un vehiculo: ubicacion, recorridos, evidencias, captura y limite de velocidad
class PantallaVehiculo extends StatefulWidget {
  const PantallaVehiculo({super.key, required this.dispositivo});

  final Dispositivo dispositivo;

  @override
  State<PantallaVehiculo> createState() => _PantallaVehiculoState();
}

class _PantallaVehiculoState extends State<PantallaVehiculo> {
  late Dispositivo _d = widget.dispositivo;

  /// Cambia despues de cada captura para que las listas se vuelvan a consultar
  int _recarga = 0;

  Future<void> _capturar() async {
    await elegirCaptura(context, _d);
    if (mounted) setState(() => _recarga++);
  }

  Future<void> _editarLimite() async {
    final texto = await pedirTexto(
      context,
      titulo: 'Límite de velocidad',
      inicial: '${_d.limiteVelocidadKmh}',
      ayuda: 'Entre 10 y 200 km/h',
      sufijo: 'km/h',
      numero: true,
    );
    if (texto == null || !mounted) return;
    final limite = int.tryParse(texto);
    if (limite == null || limite < 10 || limite > 200) {
      avisar(context, 'El límite debe ser un número entre 10 y 200');
      return;
    }
    try {
      await cambiarLimite(_d.id, limite);
      if (!mounted) return;
      setState(() => _d = _d.conLimite(limite));
      avisar(context, 'Límite actualizado a $limite km/h; el vehículo lo aplicará en unos segundos');
    } catch (e) {
      if (mounted) avisar(context, e);
    }
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 3,
      child: Scaffold(
        appBar: AppBar(
          title: Text(_d.nombre),
          actions: [
            IconButton(
              tooltip: 'Límite de velocidad',
              icon: const Icon(Icons.speed),
              onPressed: _editarLimite,
            ),
          ],
          bottom: const TabBar(
            tabs: [
              Tab(icon: Icon(Icons.location_on_outlined), text: 'Ubicación'),
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
            PantallaUbicacion(key: ValueKey('ubicacion$_recarga'), dispositivo: _d),
            PantallaRecorridos(key: ValueKey('recorridos${_d.limiteVelocidadKmh}'), dispositivo: _d),
            PantallaEvidencias(key: ValueKey('evidencias$_recarga'), dispositivo: _d),
          ],
        ),
      ),
    );
  }
}
