import 'package:material_ui/material_ui.dart';

import '../sesion.dart';
import 'comunes.dart';

const largoMinimoContrasena = 8;

final _correoValido = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');

String? validarCorreo(String correo) =>
    _correoValido.hasMatch(correo.trim()) ? null : 'Escribe un correo válido';

String? validarContrasena(String contrasena, String confirmacion) {
  if (contrasena.length < largoMinimoContrasena) {
    return 'La contraseña debe tener al menos $largoMinimoContrasena caracteres';
  }
  if (contrasena != confirmacion) return 'Las contraseñas no coinciden';
  return null;
}

void irAlInicio(BuildContext context) =>
    Navigator.of(context).pushNamedAndRemoveUntil('/inicio', (_) => false);

/// Estructura comun de las pantallas de cuenta: fondo blanco, ancho limitado y desplazable
class _MarcoCuenta extends StatelessWidget {
  const _MarcoCuenta({required this.titulo, required this.hijos});

  final String titulo;
  final List<Widget> hijos;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(title: Text(titulo)),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 400),
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: hijos),
            ),
          ),
        ),
      ),
    );
  }
}

class _Error extends StatelessWidget {
  const _Error(this.mensaje);

  final String? mensaje;

  @override
  Widget build(BuildContext context) {
    if (mensaje == null) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 16),
      child: Text(mensaje!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
    );
  }
}

class _BotonPrincipal extends StatelessWidget {
  const _BotonPrincipal({required this.texto, required this.cargando, required this.alPresionar});

  final String texto;
  final bool cargando;
  final VoidCallback alPresionar;

  @override
  Widget build(BuildContext context) {
    return FilledButton(
      onPressed: cargando ? null : alPresionar,
      child: cargando
          ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
          : Text(texto),
    );
  }
}

/// Registro de un supervisor nuevo
class PantallaCrearCuenta extends StatefulWidget {
  const PantallaCrearCuenta({super.key});

  @override
  State<PantallaCrearCuenta> createState() => _PantallaCrearCuentaState();
}

class _PantallaCrearCuentaState extends State<PantallaCrearCuenta> {
  final _nombre = TextEditingController();
  final _correo = TextEditingController();
  final _contrasena = TextEditingController();
  final _confirmacion = TextEditingController();
  bool _cargando = false;
  bool _ocultar = true;
  String? _error;

  @override
  void dispose() {
    for (final c in [_nombre, _correo, _contrasena, _confirmacion]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _crear() async {
    final problema = _nombre.text.trim().isEmpty
        ? 'Escribe tu nombre'
        : validarCorreo(_correo.text) ?? validarContrasena(_contrasena.text, _confirmacion.text);
    if (problema != null) {
      setState(() => _error = problema);
      return;
    }
    setState(() {
      _cargando = true;
      _error = null;
    });
    try {
      final conSesion = await crearCuenta(_nombre.text, _correo.text, _contrasena.text);
      if (!mounted) return;
      if (conSesion) {
        irAlInicio(context);
      } else {
        await Navigator.of(context).push(MaterialPageRoute<void>(
          builder: (_) => PantallaVerificarCorreo(correo: _correo.text.trim()),
        ));
        if (mounted) setState(() => _cargando = false);
      }
    } on ErrorApp catch (e) {
      if (mounted) {
        setState(() {
          _cargando = false;
          _error = e.mensaje;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return _MarcoCuenta(titulo: 'Crear cuenta', hijos: [
      Text('Crea tu cuenta de supervisor para ver y administrar tus vehículos.',
          style: Theme.of(context).textTheme.bodyMedium),
      const SizedBox(height: 24),
      TextField(
        controller: _nombre,
        enabled: !_cargando,
        textCapitalization: TextCapitalization.words,
        textInputAction: TextInputAction.next,
        decoration: const InputDecoration(labelText: 'Nombre'),
      ),
      const SizedBox(height: 16),
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
        obscureText: _ocultar,
        textInputAction: TextInputAction.next,
        decoration: InputDecoration(
          labelText: 'Contraseña',
          helperText: 'Al menos $largoMinimoContrasena caracteres',
          suffixIcon: IconButton(
            tooltip: _ocultar ? 'Mostrar' : 'Ocultar',
            icon: Icon(_ocultar ? Icons.visibility_outlined : Icons.visibility_off_outlined),
            onPressed: () => setState(() => _ocultar = !_ocultar),
          ),
        ),
      ),
      const SizedBox(height: 16),
      TextField(
        controller: _confirmacion,
        enabled: !_cargando,
        obscureText: _ocultar,
        textInputAction: TextInputAction.done,
        onSubmitted: (_) => _crear(),
        decoration: const InputDecoration(labelText: 'Confirmar contraseña'),
      ),
      _Error(_error),
      const SizedBox(height: 24),
      _BotonPrincipal(texto: 'Crear cuenta', cargando: _cargando, alPresionar: _crear),
    ]);
  }
}

/// Confirma el correo con el codigo que envia Supabase al crear la cuenta
class PantallaVerificarCorreo extends StatefulWidget {
  const PantallaVerificarCorreo({super.key, required this.correo});

  final String correo;

  @override
  State<PantallaVerificarCorreo> createState() => _PantallaVerificarCorreoState();
}

class _PantallaVerificarCorreoState extends State<PantallaVerificarCorreo> {
  final _codigo = TextEditingController();
  bool _cargando = false;
  String? _error;

  @override
  void dispose() {
    _codigo.dispose();
    super.dispose();
  }

  Future<void> _verificar() async {
    if (_codigo.text.trim().length < 6) {
      setState(() => _error = 'Escribe el código que llegó a tu correo');
      return;
    }
    setState(() {
      _cargando = true;
      _error = null;
    });
    try {
      await verificarCodigo(widget.correo, _codigo.text, 'email');
      if (mounted) irAlInicio(context);
    } on ErrorApp catch (e) {
      if (mounted) {
        setState(() {
          _cargando = false;
          _error = e.mensaje;
        });
      }
    }
  }

  Future<void> _reenviar() async {
    try {
      await reenviarCodigoRegistro(widget.correo);
      if (mounted) avisar(context, 'Te enviamos un código nuevo');
    } on ErrorApp catch (e) {
      if (mounted) avisar(context, e);
    }
  }

  @override
  Widget build(BuildContext context) {
    return _MarcoCuenta(titulo: 'Confirma tu correo', hijos: [
      const Icon(Icons.mark_email_unread_outlined, size: 56),
      const SizedBox(height: 16),
      Text('Enviamos un código a ${widget.correo}. Escríbelo aquí para activar tu cuenta. '
          'Si no lo ves, revisa la carpeta de spam.'),
      const SizedBox(height: 24),
      TextField(
        controller: _codigo,
        enabled: !_cargando,
        keyboardType: TextInputType.number,
        textAlign: TextAlign.center,
        maxLength: 10,
        style: Theme.of(context).textTheme.headlineSmall,
        onSubmitted: (_) => _verificar(),
        decoration: const InputDecoration(labelText: 'Código', counterText: ''),
      ),
      _Error(_error),
      const SizedBox(height: 24),
      _BotonPrincipal(texto: 'Confirmar', cargando: _cargando, alPresionar: _verificar),
      const SizedBox(height: 8),
      TextButton(onPressed: _cargando ? null : _reenviar, child: const Text('Enviar otro código')),
    ]);
  }
}

/// Paso 1 de la recuperacion: pedir el codigo por correo
class PantallaRecuperarContrasena extends StatefulWidget {
  const PantallaRecuperarContrasena({super.key, this.correoInicial = ''});

  final String correoInicial;

  @override
  State<PantallaRecuperarContrasena> createState() => _PantallaRecuperarContrasenaState();
}

class _PantallaRecuperarContrasenaState extends State<PantallaRecuperarContrasena> {
  late final _correo = TextEditingController(text: widget.correoInicial);
  bool _cargando = false;
  String? _error;

  @override
  void dispose() {
    _correo.dispose();
    super.dispose();
  }

  Future<void> _enviar() async {
    final problema = validarCorreo(_correo.text);
    if (problema != null) {
      setState(() => _error = problema);
      return;
    }
    setState(() {
      _cargando = true;
      _error = null;
    });
    try {
      await solicitarRecuperacion(_correo.text);
      if (!mounted) return;
      await Navigator.of(context).push(MaterialPageRoute<void>(
        builder: (_) => PantallaNuevaContrasena(correo: _correo.text.trim()),
      ));
      if (mounted) setState(() => _cargando = false);
    } on ErrorApp catch (e) {
      if (mounted) {
        setState(() {
          _cargando = false;
          _error = e.mensaje;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return _MarcoCuenta(titulo: 'Recuperar contraseña', hijos: [
      const Text('Escribe el correo de tu cuenta y te enviaremos un código para crear una '
          'contraseña nueva.'),
      const SizedBox(height: 24),
      TextField(
        controller: _correo,
        enabled: !_cargando,
        keyboardType: TextInputType.emailAddress,
        textInputAction: TextInputAction.done,
        onSubmitted: (_) => _enviar(),
        decoration: const InputDecoration(labelText: 'Correo'),
      ),
      _Error(_error),
      const SizedBox(height: 24),
      _BotonPrincipal(texto: 'Enviar código', cargando: _cargando, alPresionar: _enviar),
    ]);
  }
}

/// Paso 2 de la recuperacion: codigo del correo y contrasena nueva
class PantallaNuevaContrasena extends StatefulWidget {
  const PantallaNuevaContrasena({super.key, required this.correo});

  final String correo;

  @override
  State<PantallaNuevaContrasena> createState() => _PantallaNuevaContrasenaState();
}

class _PantallaNuevaContrasenaState extends State<PantallaNuevaContrasena> {
  final _codigo = TextEditingController();
  final _contrasena = TextEditingController();
  final _confirmacion = TextEditingController();
  bool _cargando = false;
  bool _ocultar = true;
  String? _error;

  @override
  void dispose() {
    for (final c in [_codigo, _contrasena, _confirmacion]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _guardar() async {
    final problema = _codigo.text.trim().length < 6
        ? 'Escribe el código que llegó a tu correo'
        : validarContrasena(_contrasena.text, _confirmacion.text);
    if (problema != null) {
      setState(() => _error = problema);
      return;
    }
    setState(() {
      _cargando = true;
      _error = null;
    });
    try {
      await verificarCodigo(widget.correo, _codigo.text, 'recovery');
      await cambiarContrasena(_contrasena.text);
      if (!mounted) return;
      avisar(context, 'Contraseña actualizada');
      irAlInicio(context);
    } on ErrorApp catch (e) {
      if (mounted) {
        setState(() {
          _cargando = false;
          _error = e.mensaje;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return _MarcoCuenta(titulo: 'Contraseña nueva', hijos: [
      Text('Enviamos un código a ${widget.correo}. Si no lo ves, revisa la carpeta de spam.'),
      const SizedBox(height: 24),
      TextField(
        controller: _codigo,
        enabled: !_cargando,
        keyboardType: TextInputType.number,
        textInputAction: TextInputAction.next,
        maxLength: 10,
        decoration: const InputDecoration(labelText: 'Código', counterText: ''),
      ),
      const SizedBox(height: 16),
      TextField(
        controller: _contrasena,
        enabled: !_cargando,
        obscureText: _ocultar,
        textInputAction: TextInputAction.next,
        decoration: InputDecoration(
          labelText: 'Contraseña nueva',
          helperText: 'Al menos $largoMinimoContrasena caracteres',
          suffixIcon: IconButton(
            tooltip: _ocultar ? 'Mostrar' : 'Ocultar',
            icon: Icon(_ocultar ? Icons.visibility_outlined : Icons.visibility_off_outlined),
            onPressed: () => setState(() => _ocultar = !_ocultar),
          ),
        ),
      ),
      const SizedBox(height: 16),
      TextField(
        controller: _confirmacion,
        enabled: !_cargando,
        obscureText: _ocultar,
        textInputAction: TextInputAction.done,
        onSubmitted: (_) => _guardar(),
        decoration: const InputDecoration(labelText: 'Confirmar contraseña'),
      ),
      _Error(_error),
      const SizedBox(height: 24),
      _BotonPrincipal(texto: 'Guardar contraseña', cargando: _cargando, alPresionar: _guardar),
    ]);
  }
}
