import 'package:dashguard/main.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('muestra las secciones principales', (tester) async {
    await tester.pumpWidget(const DashGuardApp());
    await tester.pump();

    for (final seccion in ['Vehículos', 'Recorridos', 'Alertas', 'Evidencias']) {
      expect(find.text(seccion), findsWidgets);
    }
  });
}
