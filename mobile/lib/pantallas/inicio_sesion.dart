import 'package:material_ui/material_ui.dart';

import '../sesion.dart';
import 'cuenta.dart';

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
      if (e.codigo == 'email_not_confirmed') await _confirmarCorreo();
    }
  }

  /// La cuenta existe pero falta confirmar el correo: se manda un codigo nuevo
  Future<void> _confirmarCorreo() async {
    final correo = _correo.text.trim();
    try {
      await reenviarCodigoRegistro(correo);
    } on ErrorApp {
      // aun sin codigo nuevo puede usar el que ya le llego
    }
    if (!mounted) return;
    setState(() => _error = null);
    await Navigator.of(context).push(MaterialPageRoute<void>(
      builder: (_) => PantallaVerificarCorreo(correo: correo),
    ));
  }

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return Scaffold(
      // blanco para que combine con el fondo del logo
      backgroundColor: Colors.white,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 400),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Image.asset('assets/logo/logo_completo.png', height: 170, semanticLabel: 'DashGuard'),
                  const SizedBox(height: 16),
                  Text('Acceso del supervisor',
                      textAlign: TextAlign.center, style: tema.textTheme.titleMedium),
                  const SizedBox(height: 32),
                  TextField(
                    controller: _correo,
                    enabled: !_cargando,
                    keyboardType: TextInputType.emailAddress,
                    textInputAction: TextInputAction.next,
                    decoration: const InputDecoration(labelText: 'Correo'),
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: _contrasena,
                    enabled: !_cargando,
                    obscureText: true,
                    textInputAction: TextInputAction.done,
                    onSubmitted: (_) => _entrar(),
                    decoration: const InputDecoration(labelText: 'Contraseña'),
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
                  const SizedBox(height: 8),
                  TextButton(
                    onPressed: _cargando
                        ? null
                        : () => Navigator.of(context).push(MaterialPageRoute<void>(
                              builder: (_) =>
                                  PantallaRecuperarContrasena(correoInicial: _correo.text.trim()),
                            )),
                    child: const Text('¿Olvidaste tu contraseña?'),
                  ),
                  const SizedBox(height: 24),
                  const Divider(),
                  const SizedBox(height: 16),
                  const Text('¿Todavía no tienes cuenta?', textAlign: TextAlign.center),
                  const SizedBox(height: 8),
                  OutlinedButton(
                    onPressed: _cargando
                        ? null
                        : () => Navigator.of(context).push(MaterialPageRoute<void>(
                              builder: (_) => const PantallaCrearCuenta(),
                            )),
                    child: const Text('Crear cuenta'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
