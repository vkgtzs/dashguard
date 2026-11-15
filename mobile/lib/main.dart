import 'package:material_ui/material_ui.dart';

import 'pantallas/recorridos.dart';
import 'pantallas/vehiculos.dart';

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
      home: const Inicio(),
    );
  }
}

/// Pantalla principal, barra inferior con las cuatro secciones
class Inicio extends StatefulWidget {
  const Inicio({super.key});

  @override
  State<Inicio> createState() => _InicioState();
}

class _InicioState extends State<Inicio> {
  int _indice = 0;

  static const _titulos = ['Vehículos', 'Recorridos', 'Alertas', 'Evidencias'];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(_titulos[_indice])),
      body: IndexedStack(
        index: _indice,
        children: const [
          PantallaVehiculos(),
          PantallaRecorridos(),
          _Pendiente(icono: Icons.notifications_outlined, texto: 'Aquí irán las alertas'),
          _Pendiente(icono: Icons.photo_camera_outlined, texto: 'Aquí irán las fotos y videos'),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _indice,
        onDestinationSelected: (i) => setState(() => _indice = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.directions_car_outlined), label: 'Vehículos'),
          NavigationDestination(icon: Icon(Icons.route_outlined), label: 'Recorridos'),
          NavigationDestination(icon: Icon(Icons.notifications_outlined), label: 'Alertas'),
          NavigationDestination(icon: Icon(Icons.photo_camera_outlined), label: 'Evidencias'),
        ],
      ),
    );
  }
}

/// Relleno temporal para las secciones que todavaa no estan hechas
class _Pendiente extends StatelessWidget {
  const _Pendiente({required this.icono, required this.texto});

  final IconData icono;
  final String texto;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icono, size: 48, color: Theme.of(context).colorScheme.outline),
          const SizedBox(height: 12),
          Text(texto),
        ],
      ),
    );
  }
}
