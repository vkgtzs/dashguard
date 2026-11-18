import 'package:material_ui/material_ui.dart';

import '../datos.dart';
import '../formato.dart';
import '../modelos.dart';
import 'comunes.dart';
import 'mapa_recorrido.dart';

/// Lista de recorridos de un vehiculo
class PantallaRecorridos extends StatelessWidget {
  const PantallaRecorridos({super.key, required this.dispositivo});

  final Dispositivo dispositivo;

  @override
  Widget build(BuildContext context) {
    final d = dispositivo;
    return ListaPaginada<Sesion>(
      cargar: (antes) => obtenerSesiones(d.id, antes: antes),
      fecha: (s) => s.inicio,
      vacio: 'Este vehículo todavía no tiene recorridos',
      espacioFinal: 88,
      elemento: (context, s) => Card(
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
      ),
    );
  }
}
