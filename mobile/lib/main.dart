import 'package:material_ui/material_ui.dart';

import 'pantallas/alertas.dart';
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

  /// Cambia al entrar a otra seccion para que Alertas y Evidencias se vuelvan a consultar
  int _recarga = 0;

  static const _titulos = ['Vehículos', 'Alertas', 'Evidencias'];

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
          const PantallaVehiculos(),
          PantallaAlertas(key: ValueKey('alertas$_recarga')),
          PantallaEvidencias(key: ValueKey('evidencias$_recarga')),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _indice,
        onDestinationSelected: (i) => setState(() {
          if (i != _indice) _recarga++;
          _indice = i;
        }),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.directions_car_outlined), label: 'Vehículos'),
          NavigationDestination(icon: Icon(Icons.notifications_outlined), label: 'Alertas'),
          NavigationDestination(icon: Icon(Icons.photo_camera_outlined), label: 'Evidencias'),
        ],
      ),
    );
  }
}
