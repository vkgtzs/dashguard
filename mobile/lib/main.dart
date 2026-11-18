import 'dart:async';

import 'package:material_ui/material_ui.dart';

import 'datos.dart';

import 'pantallas/alertas.dart';
import 'pantallas/conductores.dart';
import 'pantallas/evidencias.dart';
import 'pantallas/inicio_sesion.dart';
import 'pantallas/vehiculos.dart';
import 'sesion.dart';

void main() => runApp(const DashGuardApp());

class DashGuardApp extends StatelessWidget {
  const DashGuardApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'DashGuard',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF175FA6)),
      ),
      home: const PantallaInicioSesion(),
      routes: {'/inicio': (_) => const Inicio()},
    );
  }
}

/// Pantalla principal, barra inferior con las secciones
class Inicio extends StatefulWidget {
  const Inicio({super.key});

  @override
  State<Inicio> createState() => _InicioState();
}

class _InicioState extends State<Inicio> {
  int _indice = 0;

  /// Cambia al entrar a otra seccion para que se vuelva a consultar
  int _recarga = 0;

  /// Alertas sin leer, se muestran en la barra inferior
  int _pendientes = 0;
  Timer? _reloj;

  static const _titulos = ['Vehículos', 'Alertas', 'Evidencias', 'Conductores'];
  static const _cadaCuantoAlertas = Duration(minutes: 1);

  @override
  void initState() {
    super.initState();
    _contarAlertas();
    _reloj = Timer.periodic(_cadaCuantoAlertas, (_) => _contarAlertas());
  }

  @override
  void dispose() {
    _reloj?.cancel();
    super.dispose();
  }

  Future<void> _contarAlertas() async {
    try {
      final pendientes = await alertasPendientes();
      if (mounted) setState(() => _pendientes = pendientes);
    } catch (_) {
      // sin conexion se conserva el ultimo valor
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_titulos[_indice]),
        actions: [
          IconButton(
            tooltip: 'Cerrar sesión',
            icon: const Icon(Icons.logout),
            onPressed: () {
              cerrarSesion();
              Navigator.of(context).pushReplacement(
                MaterialPageRoute<void>(builder: (_) => const PantallaInicioSesion()),
              );
            },
          ),
        ],
      ),
      body: IndexedStack(
        index: _indice,
        children: [
          PantallaVehiculos(key: ValueKey('vehiculos$_recarga')),
          PantallaAlertas(key: ValueKey('alertas$_recarga'), alLeer: _contarAlertas),
          PantallaEvidencias(key: ValueKey('evidencias$_recarga')),
          PantallaConductores(key: ValueKey('conductores$_recarga')),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _indice,
        onDestinationSelected: (i) => setState(() {
          if (i != _indice) _recarga++;
          _indice = i;
          _contarAlertas();
        }),
        destinations: [
          const NavigationDestination(icon: Icon(Icons.directions_car_outlined), label: 'Vehículos'),
          NavigationDestination(
            icon: Badge(
              isLabelVisible: _pendientes > 0,
              label: Text(_pendientes > 99 ? '99+' : '$_pendientes'),
              child: const Icon(Icons.notifications_outlined),
            ),
            label: 'Alertas',
          ),
          const NavigationDestination(icon: Icon(Icons.photo_camera_outlined), label: 'Evidencias'),
          const NavigationDestination(icon: Icon(Icons.people_outline), label: 'Conductores'),
        ],
      ),
    );
  }
}
