import 'package:dashguard/main.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('sin sesion guardada abre en la pantalla de inicio de sesion', (tester) async {
    FlutterSecureStorage.setMockInitialValues({});
    await tester.pumpWidget(const DashGuardApp());
    await tester.pumpAndSettle();

    expect(find.text('Acceso del supervisor'), findsOneWidget);
    expect(find.text('Correo'), findsOneWidget);
    expect(find.text('Contraseña'), findsOneWidget);
    expect(find.text('Iniciar sesión'), findsOneWidget);
    expect(find.text('Crear cuenta'), findsOneWidget);
    expect(find.text('¿Olvidaste tu contraseña?'), findsOneWidget);
  });
}
