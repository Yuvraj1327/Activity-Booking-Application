import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'helpers.dart';

/// The five tabs must lay out without overflow on small and large phones.
void main() {
  for (final size in const [Size(320, 568), Size(360, 640), Size(412, 915)]) {
    testWidgets('tabs render without overflow at $size', (tester) async {
      final env = TestEnv();
      await env.pump(tester);
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1;
      await tester.pumpAndSettle();
      for (final tab in ['Home', 'Explore', 'Bookings', 'Favorites', 'Profile']) {
        await tester.tap(inNavBar(tab));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull, reason: '$tab at $size');
      }
    });
  }
}
