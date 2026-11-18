import 'package:material_ui/material_ui.dart';

import '../datos.dart';
import '../formato.dart';
import '../modelos.dart';
import '../sesion.dart';
import 'comunes.dart';

const _verde = Color(0xFF16834A);

/// Conductores de la cuenta: agregar, ver si tienen rostro registrado y abrir su detalle
class PantallaConductores extends StatefulWidget {
  const PantallaConductores({super.key});

  @override
  State<PantallaConductores> createState() => _PantallaConductoresState();
}

class _PantallaConductoresState extends State<PantallaConductores> {
  late Future<List<Conductor>> _conductores = obtenerConductores();

  Future<void> _recargar() async {
    final nuevos = obtenerConductores();
    setState(() => _conductores = nuevos);
    try {
      await nuevos;
    } catch (_) {
      // el error se muestra en la lista
    }
  }

  Future<void> _abrir(Conductor c) async {
    await Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => PantallaConductor(conductor: c)),
    );
    _recargar();
  }

  Future<void> _agregar() async {
    final nombre = await pedirTexto(context, titulo: 'Nuevo conductor', etiqueta: 'Nombre');
    if (nombre == null || nombre.isEmpty || !mounted) return;
    try {
      final conductor = await crearConductor(nombre);
      if (!mounted) return;
      avisar(context, 'Conductor agregado; ahora registra su rostro');
      await _abrir(conductor);
    } catch (e) {
      if (mounted) avisar(context, e);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _agregar,
        icon: const Icon(Icons.person_add),
        label: const Text('Agregar'),
      ),
      body: FutureBuilder<List<Conductor>>(
        future: _conductores,
        builder: (context, snapshot) {
          if (snapshot.hasError) {
            return MensajeError(error: snapshot.error, alReintentar: _recargar);
          }
          if (!snapshot.hasData) {
            return const Center(child: CircularProgressIndicator());
          }
          final conductores = snapshot.data!;
          return RefreshIndicator(
            onRefresh: _recargar,
            child: conductores.isEmpty
                ? ListView(
                    children: const [
                      SizedBox(height: 120),
                      Center(child: Text('Todavía no hay conductores')),
                    ],
                  )
                : ListView.builder(
                    padding: const EdgeInsets.fromLTRB(12, 12, 12, 88),
                    itemCount: conductores.length,
                    itemBuilder: (context, i) {
                      final c = conductores[i];
                      return Card(
                        child: ListTile(
                          leading: Icon(
                            Icons.face,
                            color: c.rostroRegistrado && c.activo
                                ? _verde
                                : Theme.of(context).colorScheme.outline,
                          ),
                          title: Text(c.nombre),
                          subtitle: Text([
                            c.rostroRegistrado ? 'Rostro registrado' : 'Sin rostro registrado',
                            if (!c.activo) 'Inactivo',
                          ].join(' · ')),
                          trailing: const Icon(Icons.chevron_right),
                          onTap: () => _abrir(c),
                        ),
                      );
                    },
                  ),
          );
        },
      ),
    );
  }
}

/// Detalle de un conductor: registrar o borrar su rostro, activarlo, renombrarlo o eliminarlo
class PantallaConductor extends StatefulWidget {
  const PantallaConductor({super.key, required this.conductor});

  final Conductor conductor;

  @override
  State<PantallaConductor> createState() => _PantallaConductorState();
}

class _PantallaConductorState extends State<PantallaConductor> {
  late Conductor _c = widget.conductor;
  bool _ocupado = false;

  Future<void> _aplicar(Future<Conductor> Function() accion, String mensaje) async {
    if (!mounted) return;
    setState(() => _ocupado = true);
    try {
      final conductor = await accion();
      if (!mounted) return;
      setState(() => _c = conductor);
      avisar(context, mensaje);
    } catch (e) {
      if (mounted) avisar(context, e);
    } finally {
      if (mounted) setState(() => _ocupado = false);
    }
  }

  Future<void> _renombrar() async {
    final nombre = await pedirTexto(context, titulo: 'Nombre del conductor', inicial: _c.nombre);
    if (nombre == null || nombre.isEmpty || nombre == _c.nombre) return;
    await _aplicar(() => actualizarConductor(_c.id, nombre: nombre), 'Nombre actualizado');
  }

  Future<void> _cambiarActivo(bool activo) => _aplicar(
        () => actualizarConductor(_c.id, activo: activo),
        activo ? 'Conductor activado' : 'Conductor desactivado: ningún vehículo lo reconocerá',
      );

  Future<void> _registrarRostro() async {
    final List<Dispositivo> dispositivos;
    try {
      dispositivos = await obtenerDispositivos();
    } catch (e) {
      if (mounted) avisar(context, e);
      return;
    }
    if (!mounted) return;
    if (dispositivos.isEmpty) {
      avisar(context, 'No tienes vehículos para registrar el rostro');
      return;
    }
    final elegido = await showModalBottomSheet<Dispositivo>(
      context: context,
      builder: (contexto) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const ListTile(title: Text('¿En qué vehículo está sentado el conductor?')),
            for (final d in dispositivos)
              ListTile(
                leading: const Icon(Icons.directions_car),
                title: Text(d.nombre),
                subtitle: Text('Última conexión: ${haceCuanto(d.vistoEn)}'),
                onTap: () => Navigator.pop(contexto, d),
              ),
          ],
        ),
      ),
    );
    if (elegido == null || !mounted) return;
    final registrado = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => PantallaRegistroRostro(conductor: _c, dispositivo: elegido)),
    );
    if (registrado != true || !mounted) return;
    try {
      final conductores = await obtenerConductores();
      if (!mounted) return;
      setState(() => _c = conductores.firstWhere((c) => c.id == _c.id, orElse: () => _c));
    } catch (_) {
      // se queda con los datos anteriores
    }
    if (mounted) avisar(context, 'Rostro registrado; todos tus vehículos lo reconocerán');
  }

  Future<void> _borrarRostro() async {
    final si = await confirmar(context,
        titulo: 'Borrar rostro',
        mensaje: 'Los vehículos dejarán de reconocer a ${_c.nombre} hasta que vuelvas a registrarlo.',
        accion: 'Borrar');
    if (si) await _aplicar(() => actualizarConductor(_c.id, borrarRostro: true), 'Rostro borrado');
  }

  Future<void> _eliminar() async {
    final si = await confirmar(context,
        titulo: 'Eliminar conductor',
        mensaje: 'Se eliminará a ${_c.nombre} y su rostro. Sus recorridos se conservan sin nombre.',
        accion: 'Eliminar');
    if (!si || !mounted) return;
    setState(() => _ocupado = true);
    try {
      await eliminarConductor(_c.id);
      if (mounted) Navigator.of(context).pop();
    } catch (e) {
      if (mounted) {
        avisar(context, e);
        setState(() => _ocupado = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final esquema = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(
        title: Text(_c.nombre),
        actions: [
          IconButton(
            tooltip: 'Cambiar nombre',
            icon: const Icon(Icons.edit_outlined),
            onPressed: _ocupado ? null : _renombrar,
          ),
        ],
        bottom: _ocupado
            ? const PreferredSize(
                preferredSize: Size.fromHeight(4), child: LinearProgressIndicator())
            : null,
      ),
      body: ListView(
        padding: const EdgeInsets.symmetric(vertical: 8),
        children: [
          ListTile(
            leading: Icon(Icons.face, color: _c.rostroRegistrado ? _verde : esquema.outline),
            title: Text(_c.rostroRegistrado ? 'Rostro registrado' : 'Sin rostro registrado'),
            subtitle: Text(_c.rostroRegistrado && _c.rostroActualizado != null
                ? 'Registrado el ${fechaHora(_c.rostroActualizado!)}'
                : 'Regístralo para que los vehículos lo reconozcan'),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: FilledButton.icon(
              onPressed: _ocupado || !_c.activo ? null : _registrarRostro,
              icon: const Icon(Icons.photo_camera_front),
              label: Text(_c.rostroRegistrado ? 'Volver a registrar rostro' : 'Registrar rostro'),
            ),
          ),
          if (!_c.activo)
            const Padding(
              padding: EdgeInsets.fromLTRB(16, 8, 16, 0),
              child: Text('Activa al conductor para registrar su rostro.'),
            ),
          if (_c.rostroRegistrado)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: TextButton.icon(
                onPressed: _ocupado ? null : _borrarRostro,
                icon: const Icon(Icons.delete_outline),
                label: const Text('Borrar rostro'),
              ),
            ),
          const Divider(height: 32),
          SwitchListTile(
            title: const Text('Activo'),
            subtitle: const Text('Los conductores inactivos no se reconocen en ningún vehículo'),
            value: _c.activo,
            onChanged: _ocupado ? null : _cambiarActivo,
          ),
          const Divider(height: 32),
          ListTile(
            leading: Icon(Icons.delete_forever_outlined, color: esquema.error),
            title: Text('Eliminar conductor', style: TextStyle(color: esquema.error)),
            onTap: _ocupado ? null : _eliminar,
          ),
        ],
      ),
    );
  }
}

/// Pide al vehiculo que registre el rostro y espera el resultado
class PantallaRegistroRostro extends StatefulWidget {
  const PantallaRegistroRostro({super.key, required this.conductor, required this.dispositivo});

  final Conductor conductor;
  final Dispositivo dispositivo;

  @override
  State<PantallaRegistroRostro> createState() => _PantallaRegistroRostroState();
}

class _PantallaRegistroRostroState extends State<PantallaRegistroRostro> {
  static const _cadaCuanto = Duration(seconds: 3);
  static const _esperaMaxima = Duration(minutes: 3);

  String _mensaje = 'Enviando solicitud...';
  Object? _error;

  @override
  void initState() {
    super.initState();
    _ejecutar();
  }

  Future<void> _ejecutar() async {
    setState(() {
      _error = null;
      _mensaje = 'Enviando solicitud...';
    });
    try {
      final comando = await solicitarRegistroRostro(widget.dispositivo.id, widget.conductor.id);
      if (!mounted) return;
      setState(() => _mensaje = 'Tomando muestras del rostro...');
      final limite = DateTime.now().add(_esperaMaxima);
      while (DateTime.now().isBefore(limite)) {
        await Future<void>.delayed(_cadaCuanto);
        if (!mounted) return;
        final (estado, _) = await consultarComando(comando.id);
        if (!mounted) return;
        switch (estado.estado) {
          case 'completado':
            Navigator.of(context).pop(true);
            return;
          case 'fallido':
            throw ErrorApp('No se pudo registrar: ${estado.error ?? 'sin detalle'}');
          case 'expirado':
            throw const ErrorApp(
                'El vehículo no respondió a tiempo. Puede estar apagado o sin conexión.');
        }
      }
      throw const ErrorApp('El registro tardó demasiado; revisa el conductor más tarde');
    } catch (e) {
      if (mounted) setState(() => _error = e);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Registrar a ${widget.conductor.nombre}')),
      body: _error != null
          ? MensajeError(error: _error, alReintentar: _ejecutar)
          : Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const CircularProgressIndicator(),
                    const SizedBox(height: 20),
                    Text(_mensaje, style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 12),
                    Text(
                      '${widget.conductor.nombre} debe sentarse en el lugar del conductor de '
                      '"${widget.dispositivo.nombre}" y mirar a la cámara. El LED se encenderá '
                      'mientras se toman las muestras; mover un poco la cabeza ayuda. '
                      'Tarda alrededor de un minuto.',
                      textAlign: TextAlign.center,
                    ),
                  ],
                ),
              ),
            ),
    );
  }
}
