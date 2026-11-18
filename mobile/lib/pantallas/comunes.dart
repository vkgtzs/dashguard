import 'package:material_ui/material_ui.dart';

import '../modelos.dart';

/// Mensaje de error con boton para volver a intentar
class MensajeError extends StatelessWidget {
  const MensajeError({super.key, required this.error, required this.alReintentar});

  final Object? error;
  final VoidCallback alReintentar;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.cloud_off_outlined, size: 48, color: Theme.of(context).colorScheme.outline),
            const SizedBox(height: 12),
            Text('$error', textAlign: TextAlign.center),
            const SizedBox(height: 16),
            OutlinedButton.icon(
              onPressed: alReintentar,
              icon: const Icon(Icons.refresh),
              label: const Text('Reintentar'),
            ),
          ],
        ),
      ),
    );
  }
}

/// Lista que pide sus elementos por paginas: "Cargar más" al final y deslizar hacia abajo para recargar
class ListaPaginada<T> extends StatefulWidget {
  const ListaPaginada({
    super.key,
    required this.cargar,
    required this.fecha,
    required this.elemento,
    required this.vacio,
    this.espacioFinal = 12,
  });

  /// Pide una pagina; antes es la fecha del ultimo elemento ya mostrado o null para la primera
  final Future<Pagina<T>> Function(DateTime? antes) cargar;
  final DateTime Function(T elemento) fecha;
  final Widget Function(BuildContext context, T elemento) elemento;
  final String vacio;

  /// Espacio debajo del ultimo elemento, por ejemplo para que no lo tape un boton flotante
  final double espacioFinal;

  @override
  State<ListaPaginada<T>> createState() => _ListaPaginadaState<T>();
}

class _ListaPaginadaState<T> extends State<ListaPaginada<T>> {
  final _elementos = <T>[];
  bool _cargando = true;
  bool _hayMas = false;
  Object? _error;

  @override
  void initState() {
    super.initState();
    _recargar();
  }

  Future<void> _recargar() async {
    setState(() {
      _cargando = true;
      _error = null;
    });
    try {
      final pagina = await widget.cargar(null);
      if (!mounted) return;
      setState(() {
        _elementos
          ..clear()
          ..addAll(pagina.elementos);
        _hayMas = pagina.hayMas;
      });
    } catch (e) {
      if (mounted) setState(() => _error = e);
    } finally {
      if (mounted) setState(() => _cargando = false);
    }
  }

  Future<void> _cargarMas() async {
    setState(() => _cargando = true);
    try {
      final pagina = await widget.cargar(widget.fecha(_elementos.last));
      if (!mounted) return;
      setState(() {
        _elementos.addAll(pagina.elementos);
        _hayMas = pagina.hayMas;
      });
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _cargando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_error != null && _elementos.isEmpty) {
      return MensajeError(error: _error, alReintentar: _recargar);
    }
    if (_cargando && _elementos.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    return RefreshIndicator(
      onRefresh: _recargar,
      child: _elementos.isEmpty
          ? ListView(
              children: [
                const SizedBox(height: 120),
                Center(child: Text(widget.vacio)),
              ],
            )
          : ListView.builder(
              padding: EdgeInsets.fromLTRB(12, 12, 12, widget.espacioFinal),
              itemCount: _elementos.length + (_hayMas ? 1 : 0),
              itemBuilder: (context, i) {
                if (i < _elementos.length) return widget.elemento(context, _elementos[i]);
                return Padding(
                  padding: const EdgeInsets.all(12),
                  child: Center(
                    child: _cargando
                        ? const CircularProgressIndicator()
                        : OutlinedButton.icon(
                            onPressed: _cargarMas,
                            icon: const Icon(Icons.expand_more),
                            label: const Text('Cargar más'),
                          ),
                  ),
                );
              },
            ),
    );
  }
}

/// Dialogo para escribir un texto o un numero; devuelve null si se cancela
Future<String?> pedirTexto(
  BuildContext context, {
  required String titulo,
  String inicial = '',
  String? etiqueta,
  String? ayuda,
  String? sufijo,
  bool numero = false,
}) =>
    showDialog<String>(
      context: context,
      builder: (_) => _DialogoTexto(
        titulo: titulo,
        inicial: inicial,
        etiqueta: etiqueta,
        ayuda: ayuda,
        sufijo: sufijo,
        numero: numero,
      ),
    );

class _DialogoTexto extends StatefulWidget {
  const _DialogoTexto({
    required this.titulo,
    required this.inicial,
    required this.numero,
    this.etiqueta,
    this.ayuda,
    this.sufijo,
  });

  final String titulo;
  final String inicial;
  final bool numero;
  final String? etiqueta;
  final String? ayuda;
  final String? sufijo;

  @override
  State<_DialogoTexto> createState() => _DialogoTextoState();
}

class _DialogoTextoState extends State<_DialogoTexto> {
  late final _control = TextEditingController(text: widget.inicial);

  @override
  void dispose() {
    _control.dispose();
    super.dispose();
  }

  void _aceptar() => Navigator.pop(context, _control.text.trim());

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(widget.titulo),
      content: TextField(
        controller: _control,
        autofocus: true,
        keyboardType: widget.numero ? TextInputType.number : TextInputType.text,
        textCapitalization: widget.numero ? TextCapitalization.none : TextCapitalization.words,
        decoration: InputDecoration(
          labelText: widget.etiqueta,
          helperText: widget.ayuda,
          suffixText: widget.sufijo,
        ),
        onSubmitted: (_) => _aceptar(),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancelar')),
        FilledButton(onPressed: _aceptar, child: const Text('Guardar')),
      ],
    );
  }
}

/// Pregunta antes de una accion que no se puede deshacer
Future<bool> confirmar(BuildContext context,
        {required String titulo, required String mensaje, required String accion}) async =>
    await showDialog<bool>(
      context: context,
      builder: (contexto) => AlertDialog(
        title: Text(titulo),
        content: Text(mensaje),
        actions: [
          TextButton(onPressed: () => Navigator.pop(contexto, false), child: const Text('Cancelar')),
          FilledButton(onPressed: () => Navigator.pop(contexto, true), child: Text(accion)),
        ],
      ),
    ) ??
    false;

void avisar(BuildContext context, Object mensaje) =>
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$mensaje')));
