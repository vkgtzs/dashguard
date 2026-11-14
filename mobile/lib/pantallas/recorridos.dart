import 'dart:async';

import 'package:material_ui/material_ui.dart';

import '../datos.dart';
import '../formato.dart';
import '../modelos.dart';
import 'mapa_recorrido.dart';

/// Lista de recorridos (sesiones). Al tocar uno se abre su ruta en el mapa.
class PantallaRecorridos extends StatefulWidget {
  const PantallaRecorridos({super.key});

  @override
  State<PantallaRecorridos> createState() => _PantallaRecorridosState();
}

class _PantallaRecorridosState extends State<PantallaRecorridos> {
  late final Future<(List<Sesion>, List<Dispositivo>)> _datos =
      (obtenerSesiones(), obtenerDispositivos()).wait;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<(List<Sesion>, List<Dispositivo>)>(
      future: _datos,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return const Center(child: Text('No se pudieron cargar los recorridos'));
        }
        if (!snapshot.hasData) {
          return const Center(child: CircularProgressIndicator());
        }
        final (sesiones, dispositivos) = snapshot.data!;
        if (sesiones.isEmpty) {
          return const Center(child: Text('Todavía no hay recorridos'));
        }
        final porId = {for (final d in dispositivos) d.id: d};
        return ListView.builder(
          padding: const EdgeInsets.all(12),
          itemCount: sesiones.length,
          itemBuilder: (context, i) {
            final s = sesiones[i];
            final dispositivo = porId[s.dispositivoId];
            return Card(
              child: ListTile(
                leading: Icon(
                  iconoVerificacion(s.verificacion),
                  color: colorVerificacion(s.verificacion),
                ),
                title: Text('${dispositivo?.nombre ?? s.dispositivoId} · ${fechaHora(s.inicio)}'),
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
                      nombreVehiculo: dispositivo?.nombre ?? s.dispositivoId,
                      limiteKmh: dispositivo?.limiteVelocidadKmh,
                    ),
                  ),
                ),
              ),
            );
          },
        );
      },
    );
  }
}
