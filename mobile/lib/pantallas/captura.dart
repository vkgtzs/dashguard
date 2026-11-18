import 'package:material_ui/material_ui.dart';

import '../datos.dart';
import '../modelos.dart';
import '../sesion.dart';
import 'comunes.dart';
import 'evidencias.dart';

/// Pregunta si se quiere foto o video y abre la pantalla de espera
Future<void> elegirCaptura(BuildContext context, Dispositivo dispositivo) async {
  final tipo = await showModalBottomSheet<String>(
    context: context,
    builder: (contexto) => SafeArea(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          ListTile(
            leading: const Icon(Icons.photo_camera_outlined),
            title: const Text('Tomar foto'),
            onTap: () => Navigator.pop(contexto, 'foto'),
          ),
          ListTile(
            leading: const Icon(Icons.videocam_outlined),
            title: const Text('Grabar video de 10 segundos'),
            onTap: () => Navigator.pop(contexto, 'video'),
          ),
        ],
      ),
    ),
  );
  if (tipo == null || !context.mounted) return;
  await Navigator.of(context).push(
    MaterialPageRoute<void>(
      builder: (_) => PantallaCaptura(dispositivo: dispositivo, tipo: tipo),
    ),
  );
}

/// Envia la solicitud al vehiculo y espera a que llegue la evidencia
class PantallaCaptura extends StatefulWidget {
  const PantallaCaptura({super.key, required this.dispositivo, required this.tipo});

  final Dispositivo dispositivo;
  final String tipo;

  @override
  State<PantallaCaptura> createState() => _PantallaCapturaState();
}

class _PantallaCapturaState extends State<PantallaCaptura> {
  static const _cadaCuanto = Duration(seconds: 3);
  static const _esperaMaxima = Duration(minutes: 3);

  String _mensaje = 'Enviando solicitud...';
  Object? _error;

  @override
  void initState() {
    super.initState();
    _ejecutar();
  }

  Future<void> _ejecutar() async {
    setState(() {
      _error = null;
      _mensaje = 'Enviando solicitud...';
    });
    try {
      final comando = await solicitarCaptura(widget.dispositivo.id, widget.tipo);
      if (!mounted) return;
      setState(() => _mensaje = 'Esperando al vehículo...');
      final limite = DateTime.now().add(_esperaMaxima);
      while (DateTime.now().isBefore(limite)) {
        await Future<void>.delayed(_cadaCuanto);
        if (!mounted) return;
        final (estado, evidencia) = await consultarComando(comando.id);
        if (!mounted) return;
        switch (estado.estado) {
          case 'completado' when evidencia != null:
            Navigator.of(context).pushReplacement(
              MaterialPageRoute<void>(
                builder: (_) => PantallaEvidencia(
                  evidencia: evidencia,
                  nombreVehiculo: widget.dispositivo.nombre,
                ),
              ),
            );
            return;
          case 'fallido':
            throw ErrorApp('El vehículo no pudo capturar: ${estado.error ?? 'sin detalle'}');
          case 'expirado':
            throw const ErrorApp(
                'El vehículo no respondió a tiempo. Puede estar apagado o sin conexión.');
        }
      }
      throw const ErrorApp('La evidencia tardó demasiado en llegar, revisa la pestaña Evidencias más tarde');
    } catch (e) {
      if (mounted) setState(() => _error = e);
    }
  }

  @override
  Widget build(BuildContext context) {
    final esFoto = widget.tipo == 'foto';
    return Scaffold(
      appBar: AppBar(title: Text(esFoto ? 'Tomar foto' : 'Grabar video')),
      body: _error != null
          ? MensajeError(error: _error, alReintentar: _ejecutar)
          : Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const CircularProgressIndicator(),
                    const SizedBox(height: 20),
                    Text(_mensaje, style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 8),
                    Text(
                      esFoto
                          ? 'Suele tardar menos de 30 segundos.'
                          : 'El video dura 10 segundos; puede tardar hasta un minuto.',
                      textAlign: TextAlign.center,
                    ),
                  ],
                ),
              ),
            ),
    );
  }
}
