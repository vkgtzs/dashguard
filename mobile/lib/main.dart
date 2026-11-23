import 'dart:async';

import 'package:material_ui/material_ui.dart';

import 'datos.dart';

import 'pantallas/alertas.dart';
import 'pantallas/conductores.dart';
import 'pantallas/evidencias.dart';
import 'pantallas/inicio_sesion.dart';
import 'pantallas/vehiculos.dart';
import 'sesion.dart';
import 'tema.dart';

void main() => runApp(const DashGuardApp());

class DashGuardApp extends StatelessWidget {
  const DashGuardApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'DashGuard',
      debugShowCheckedModeBanner: false,
      theme: temaDashGuard(),
      // Letras un poco mas grandes en toda la app, respetando la configuracion del telefono
      builder: (context, child) {
        final datos = MediaQuery.of(context);
        return MediaQuery(
          data: datos.copyWith(textScaler: TextScaler.linear(datos.textScaler.scale(1) * escalaTexto)),
          child: child!,
        );
      },
      home: const PantallaArranque(),
      routes: {'/inicio': (_) => const Inicio()},
    );
  }
}

/// Al abrir la app: si hay una sesion guardada entra directo, si no muestra el inicio de sesion
class PantallaArranque extends StatefulWidget {
  const PantallaArranque({super.key});

  @override
  State<PantallaArranque> createState() => _PantallaArranqueState();
}

class _PantallaArranqueState extends State<PantallaArranque> {
  Object? _error;

  @override
  void initState() {
    super.initState();
    _restaurar();
  }

  Future<void> _restaurar() async {
    setState(() => _error = null);
    try {
      final conSesion = await restaurarSesion();
      if (!mounted) return;
      if (conSesion) {
        Navigator.of(context).pushReplacementNamed('/inicio');
      } else {
        _irAlAcceso();
      }
    } catch (e) {
      if (mounted) setState(() => _error = e);
    }
  }

  void _irAlAcceso() => Navigator.of(context).pushReplacement(
        MaterialPageRoute<void>(builder: (_) => const PantallaInicioSesion()),
      );

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Image.asset('assets/logo/logo_completo.png', height: 170, semanticLabel: 'DashGuard'),
                const SizedBox(height: 32),
                if (_error == null)
                  const CircularProgressIndicator()
                else ...[
                  Text('$_error', textAlign: TextAlign.center),
                  const SizedBox(height: 16),
                  FilledButton(onPressed: _restaurar, child: const Text('Reintentar')),
                  TextButton(onPressed: _irAlAcceso, child: const Text('Entrar con otra cuenta')),
                ],
              ],
            ),
          ),
        ),
      ),
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
        title: Row(
          children: [
            const EscudoBarra(),
            const SizedBox(width: 12),
            Text(_titulos[_indice]),
          ],
        ),
        bottom: lineaAmarilla,
        actions: [
          IconButton(
            tooltip: 'Cerrar sesión',
            icon: const Icon(Icons.logout),
            onPressed: () async {
              await cerrarSesion();
              if (!context.mounted) return;
              Navigator.of(context).pushAndRemoveUntil(
                MaterialPageRoute<void>(builder: (_) => const PantallaInicioSesion()),
                (_) => false,
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
