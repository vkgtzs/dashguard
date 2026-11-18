import 'package:material_ui/material_ui.dart';

import '../sesion.dart';

/// Pantalla de acceso del supervisor
class PantallaInicioSesion extends StatefulWidget {
  const PantallaInicioSesion({super.key});

  @override
  State<PantallaInicioSesion> createState() => _PantallaInicioSesionState();
}

class _PantallaInicioSesionState extends State<PantallaInicioSesion> {
  final _correo = TextEditingController();
  final _contrasena = TextEditingController();
  bool _cargando = false;
  String? _error;

  @override
  void dispose() {
    _correo.dispose();
    _contrasena.dispose();
    super.dispose();
  }

  Future<void> _entrar() async {
    if (_correo.text.trim().isEmpty || _contrasena.text.isEmpty) {
      setState(() => _error = 'Escribe tu correo y tu contraseña');
      return;
    }
    setState(() {
      _cargando = true;
      _error = null;
    });
    try {
      await iniciarSesion(_correo.text, _contrasena.text);
      if (!mounted) return;
      Navigator.of(context).pushReplacementNamed('/inicio');
    } on ErrorApp catch (e) {
      if (!mounted) return;
      setState(() {
        _cargando = false;
        _error = e.mensaje;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 400),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Icon(Icons.shield_outlined, size: 64, color: tema.colorScheme.primary),
                  const SizedBox(height: 12),
                  Text('DashGuard', textAlign: TextAlign.center, style: tema.textTheme.headlineMedium),
                  const SizedBox(height: 4),
                  const Text('Acceso del supervisor', textAlign: TextAlign.center),
                  const SizedBox(height: 32),
                  TextField(
                    controller: _correo,
                    enabled: !_cargando,
                    keyboardType: TextInputType.emailAddress,
                    textInputAction: TextInputAction.next,
                    decoration: const InputDecoration(
                      labelText: 'Correo',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: _contrasena,
                    enabled: !_cargando,
                    obscureText: true,
                    textInputAction: TextInputAction.done,
                    onSubmitted: (_) => _entrar(),
                    decoration: const InputDecoration(
                      labelText: 'Contraseña',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  if (_error != null) ...[
                    const SizedBox(height: 16),
                    Text(_error!, style: TextStyle(color: tema.colorScheme.error)),
                  ],
                  const SizedBox(height: 24),
                  FilledButton(
                    onPressed: _cargando ? null : _entrar,
                    child: _cargando
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Text('Iniciar sesión'),
                  ),
                  if (_cargando) ...[
                    const SizedBox(height: 12),
                    Text(
                      'La primera conexión del día puede tardar hasta un minuto',
                      textAlign: TextAlign.center,
                      style: tema.textTheme.bodySmall,
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
