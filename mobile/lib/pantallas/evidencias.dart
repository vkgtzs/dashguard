import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';

import '../datos.dart';
import '../formato.dart';
import '../modelos.dart';
import 'comunes.dart';

/// Fotos y videos de un vehiculo, o de todos si no se indica
class PantallaEvidencias extends StatefulWidget {
  const PantallaEvidencias({super.key, this.dispositivo});

  final Dispositivo? dispositivo;

  @override
  State<PantallaEvidencias> createState() => _PantallaEvidenciasState();
}

class _PantallaEvidenciasState extends State<PantallaEvidencias> {
  Map<String, String> _nombres = {};

  Future<Pagina<Evidencia>> _cargar(DateTime? antes) async {
    final d = widget.dispositivo;
    if (antes == null) _nombres = d != null ? {d.id: d.nombre} : await nombresVehiculos();
    return obtenerEvidencias(dispositivoId: d?.id, antes: antes);
  }

  @override
  Widget build(BuildContext context) {
    final general = widget.dispositivo == null;
    return ListaPaginada<Evidencia>(
      cargar: _cargar,
      fecha: (e) => e.fecha,
      vacio: 'Todavía no hay fotos ni videos',
      // espacio para que el boton Capturar no tape el ultimo elemento
      espacioFinal: 88,
      elemento: (context, e) {
        final vehiculo = _nombres[e.dispositivoId] ?? e.dispositivoId;
        return Card(
          child: ListTile(
            leading: Icon(iconoEvidencia(e.tipo)),
            title: Text('${textoEvidencia(e.tipo)} · ${fechaHora(e.fecha)}'),
            subtitle: Text([if (general) vehiculo, tamano(e.bytes)]
                .whereType<String>()
                .where((t) => t.isNotEmpty)
                .join(' · ')),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => PantallaEvidencia(evidencia: e, nombreVehiculo: vehiculo),
              ),
            ),
          ),
        );
      },
    );
  }
}

/// Muestra una foto o permite abrir un video, con su fecha y ubicacion
class PantallaEvidencia extends StatefulWidget {
  const PantallaEvidencia({super.key, required this.evidencia, this.nombreVehiculo});

  final Evidencia evidencia;
  final String? nombreVehiculo;

  @override
  State<PantallaEvidencia> createState() => _PantallaEvidenciaState();
}

class _PantallaEvidenciaState extends State<PantallaEvidencia> {
  late Future<String> _url = urlEvidencia(widget.evidencia.id);

  Future<void> _abrir(Future<String> Function() enlace) async {
    try {
      final abierto =
          await launchUrl(Uri.parse(await enlace()), mode: LaunchMode.externalApplication);
      if (!abierto) throw Exception('No hay una aplicación para abrirlo');
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final e = widget.evidencia;
    final esFoto = e.tipo == 'foto';
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.nombreVehiculo == null
            ? textoEvidencia(e.tipo)
            : '${textoEvidencia(e.tipo)} · ${widget.nombreVehiculo}'),
      ),
      body: Column(
        children: [
          Expanded(
            child: esFoto
                ? FutureBuilder<String>(
                    future: _url,
                    builder: (context, snapshot) {
                      if (snapshot.hasError) {
                        return MensajeError(
                          error: snapshot.error,
                          alReintentar: () => setState(() => _url = urlEvidencia(e.id)),
                        );
                      }
                      if (!snapshot.hasData) {
                        return const Center(child: CircularProgressIndicator());
                      }
                      return InteractiveViewer(
                        maxScale: 5,
                        child: Center(
                          child: Image.network(
                            snapshot.data!,
                            loadingBuilder: (context, imagen, progreso) => progreso == null
                                ? imagen
                                : const Center(child: CircularProgressIndicator()),
                            errorBuilder: (context, error, pila) =>
                                const Text('No se pudo cargar la foto'),
                          ),
                        ),
                      );
                    },
                  )
                : Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.videocam_outlined,
                            size: 64, color: Theme.of(context).colorScheme.outline),
                        const SizedBox(height: 16),
                        FilledButton.icon(
                          // se pide un enlace nuevo cada vez porque vencen a los 5 minutos
                          onPressed: () => _abrir(() => urlEvidencia(e.id)),
                          icon: const Icon(Icons.play_arrow),
                          label: const Text('Reproducir video'),
                        ),
                      ],
                    ),
                  ),
          ),
          SafeArea(
            top: false,
            child: ListTile(
              leading: const Icon(Icons.schedule),
              title: Text(fechaHora(e.fecha)),
              subtitle: Text(e.latitud == null || e.longitud == null
                  ? 'Ubicación no disponible'
                  : coordenadas(e.latitud!, e.longitud!)),
              trailing: e.latitud == null || e.longitud == null
                  ? null
                  : IconButton(
                      tooltip: 'Ver en el mapa',
                      icon: const Icon(Icons.map_outlined),
                      onPressed: () => _abrir(() async =>
                          'https://www.google.com/maps/search/?api=1&query=${e.latitud},${e.longitud}'),
                    ),
            ),
          ),
        ],
      ),
    );
  }
}
