// Identidad visual de DashGuard: verde y amarillo de la universidad, fondo blanco
// y texto negro. El verde y el amarillo nunca se usan como color de texto: solo en
// fondos, botones, iconos, bordes y el logo.

import 'package:material_ui/material_ui.dart';

const verdeDashGuard = Color(0xFF00753F);
const amarilloDashGuard = Color(0xFFFBBA0F);
const verdeClaro = Color(0xFFE2F1E9);
const textoPrincipal = Color(0xFF1A1C1B);
const textoSecundario = Color(0xFF5A605C);
const fondoApp = Color(0xFFF4F7F5);
const bordeSuave = Color(0xFFDDE3DF);

/// Las letras de toda la app son 12 % mas grandes, ademas del tamano que se elija en el telefono
const escalaTexto = 1.12;

const _fuente = 'Poppins';

ThemeData temaDashGuard() {
  final esquema = ColorScheme.fromSeed(seedColor: verdeDashGuard).copyWith(
    primary: verdeDashGuard,
    onPrimary: Colors.white,
    primaryContainer: verdeClaro,
    onPrimaryContainer: textoPrincipal,
    secondary: amarilloDashGuard,
    onSecondary: textoPrincipal,
    secondaryContainer: amarilloDashGuard,
    onSecondaryContainer: textoPrincipal,
    surface: Colors.white,
    onSurface: textoPrincipal,
    onSurfaceVariant: textoSecundario,
    outline: textoSecundario,
    outlineVariant: bordeSuave,
  );
  final base = ThemeData(colorScheme: esquema, useMaterial3: true, fontFamily: _fuente);
  bool seleccionado(Set<WidgetState> estados) => estados.contains(WidgetState.selected);

  return base.copyWith(
    scaffoldBackgroundColor: fondoApp,
    textTheme: base.textTheme.apply(bodyColor: textoPrincipal, displayColor: textoPrincipal),
    appBarTheme: const AppBarThemeData(
      backgroundColor: verdeDashGuard,
      foregroundColor: Colors.white,
      elevation: 0,
      scrolledUnderElevation: 0,
      titleTextStyle: TextStyle(
          fontFamily: _fuente, fontSize: 19, fontWeight: FontWeight.w600, color: Colors.white),
    ),
    tabBarTheme: const TabBarThemeData(
      labelColor: Colors.white,
      unselectedLabelColor: Color(0xCCFFFFFF),
      indicatorColor: amarilloDashGuard,
      indicatorSize: TabBarIndicatorSize.tab,
      dividerColor: Colors.transparent,
    ),
    cardTheme: CardThemeData(
      color: Colors.white,
      elevation: 0,
      margin: const EdgeInsets.symmetric(vertical: 5),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: bordeSuave),
      ),
    ),
    floatingActionButtonTheme: const FloatingActionButtonThemeData(
      backgroundColor: amarilloDashGuard,
      foregroundColor: textoPrincipal,
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: Colors.white,
      indicatorColor: amarilloDashGuard,
      iconTheme: WidgetStateProperty.resolveWith((estados) =>
          IconThemeData(color: seleccionado(estados) ? textoPrincipal : textoSecundario)),
      labelTextStyle: WidgetStateProperty.resolveWith((estados) => TextStyle(
            fontFamily: _fuente,
            fontSize: 12,
            fontWeight: seleccionado(estados) ? FontWeight.w600 : FontWeight.w400,
            color: seleccionado(estados) ? textoPrincipal : textoSecundario,
          )),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: verdeDashGuard,
        foregroundColor: Colors.white,
        minimumSize: const Size(0, 48),
        textStyle: const TextStyle(fontFamily: _fuente, fontWeight: FontWeight.w600),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: textoPrincipal,
        side: const BorderSide(color: verdeDashGuard),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(foregroundColor: textoPrincipal),
    ),
    inputDecorationTheme: const InputDecorationThemeData(
      border: OutlineInputBorder(borderRadius: BorderRadius.all(Radius.circular(10))),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.all(Radius.circular(10)),
        borderSide: BorderSide(color: verdeDashGuard, width: 2),
      ),
      floatingLabelStyle: TextStyle(color: textoPrincipal),
    ),
    progressIndicatorTheme: const ProgressIndicatorThemeData(color: verdeDashGuard),
    badgeTheme: const BadgeThemeData(backgroundColor: verdeDashGuard, textColor: Colors.white),
    switchTheme: SwitchThemeData(
      thumbColor: WidgetStateProperty.resolveWith(
          (estados) => seleccionado(estados) ? Colors.white : null),
      trackColor: WidgetStateProperty.resolveWith(
          (estados) => seleccionado(estados) ? verdeDashGuard : null),
    ),
    listTileTheme: const ListTileThemeData(iconColor: textoSecundario, textColor: textoPrincipal),
    dividerTheme: const DividerThemeData(color: bordeSuave),
  );
}

/// Escudo de DashGuard en un recuadro blanco, para la barra superior verde
class EscudoBarra extends StatelessWidget {
  const EscudoBarra({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(3),
      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(8)),
      child: Image.asset('assets/logo/escudo.png', height: 28, semanticLabel: 'DashGuard'),
    );
  }
}

/// Linea amarilla debajo de la barra superior
const lineaAmarilla = PreferredSize(
  preferredSize: Size.fromHeight(4),
  child: ColoredBox(color: amarilloDashGuard, child: SizedBox(height: 4, width: double.infinity)),
);
