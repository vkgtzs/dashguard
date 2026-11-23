import 'package:material_ui/material_ui.dart';

import '../datos.dart';
import '../formato.dart';
import '../modelos.dart';
import 'comunes.dart';
import 'mapa_recorrido.dart';

/// Lista de recorridos de un vehiculo. Por omision oculta los que no fueron un viaje real.
class PantallaRecorridos extends StatefulWidget {
  const PantallaRecorridos({super.key, required this.dispositivo});

  final Dispositivo dispositivo;

  @override
  State<PantallaRecorridos> createState() => _PantallaRecorridosState();
}

class _PantallaRecorridosState extends State<PantallaRecorridos> {
  bool _incluirNoValidos = false;

  @override
  Widget build(BuildContext context) {
    final d = widget.dispositivo;
    return Column(
      children: [
        SwitchListTile(
          title: const Text('Mostrar recorridos sin desplazamiento'),
          subtitle: const Text('Cuando el dispositivo se movió sin hacer un viaje'),
          value: _incluirNoValidos,
          onChanged: (valor) => setState(() => _incluirNoValidos = valor),
        ),
        const Divider(height: 1),
        Expanded(
          child: ListaPaginada<Sesion>(
            key: ValueKey(_incluirNoValidos),
            cargar: (antes) =>
                obtenerSesiones(d.id, antes: antes, incluirNoValidos: _incluirNoValidos),
            fecha: (s) => s.inicio,
            vacio: 'Este vehículo todavía no tiene recorridos',
            espacioFinal: 88,
            elemento: (context, s) {
              final sinViaje = s.valido == false;
              return Card(
                child: ListTile(
                  leading: Icon(
                    sinViaje ? Icons.do_not_disturb_on_outlined : iconoVerificacion(s.verificacion),
                    color: sinViaje
                        ? Theme.of(context).colorScheme.outline
                        : colorVerificacion(s.verificacion),
                  ),
                  title: Text(fechaHora(s.inicio)),
                  subtitle: Text(
                    '${s.conductor ?? textoVerificacion(s.verificacion)}\n'
                    '${sinViaje ? 'Sin desplazamiento' : distancia(s.distanciaM)}'
                    '${s.fin == null ? ' · en curso' : ''}',
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
          ),
        ),
      ],
    );
  }
}
