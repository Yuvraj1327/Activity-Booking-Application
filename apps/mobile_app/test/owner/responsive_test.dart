import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:zuruv/core/config/app_config.dart';

import 'helpers.dart';

/// The five main Owner tabs must lay out without overflow on a small phone and with large text.
void main() {
  for (final (size, scale) in const [(Size(320, 640), 1.0), (Size(360, 740), 1.6), (Size(412, 915), 1.0)]) {
    testWidgets('tabs do not overflow at ${size.width.toInt()}x${size.height.toInt()}, text x$scale', (tester) async {
      final env = TestEnv();
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1;
      tester.platformDispatcher.textScaleFactorTestValue = scale;
      addTearDown(tester.view.reset);
      final errors = <String>[];
      final previous = FlutterError.onError;
      FlutterError.onError = (d) {
        errors.add(d.toString().split('\n').take(25).join('\n'));
      };
      addTearDown(() => FlutterError.onError = previous);
      addTearDown(tester.platformDispatcher.clearAllTestValues);
      await tester.pumpWidget(await env.app());
      await tester.pump();
      await tester.pump(AppConfig.splashDuration + const Duration(milliseconds: 100));
      await tester.pumpAndSettle();

      for (final tab in ['Dashboard', 'Venues', 'Bookings', 'Earnings', 'Profile']) {
        await tester.tap(inNavBar(tab));
        await tester.pumpAndSettle();
        // Scroll to the bottom so every row is built and laid out.
        final scrollable = find.byType(Scrollable);
        if (scrollable.evaluate().isNotEmpty) {
          await tester.drag(scrollable.last, const Offset(0, -2000));
          await tester.pumpAndSettle();
        }
        if (errors.isNotEmpty) FlutterError.onError = previous;
        expect(errors, isEmpty, reason: '$tab: ${errors.join('\n---\n')}');
      }
    });
  }
}
