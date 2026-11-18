import 'package:dashguard/main.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('abre en la pantalla de inicio de sesion', (tester) async {
    await tester.pumpWidget(const DashGuardApp());
    await tester.pump();

    expect(find.text('Acceso del supervisor'), findsOneWidget);
    expect(find.text('Correo'), findsOneWidget);
    expect(find.text('Contraseña'), findsOneWidget);
    expect(find.text('Iniciar sesión'), findsOneWidget);
  });
}
