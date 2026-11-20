import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:zuruv/customer/shared/widgets/category_icons.dart';

import 'helpers.dart';

const fifteen = [
  'cricket', 'football', 'badminton', 'tennis', 'basketball', 'volleyball', 'table_tennis', 'hockey',
  'squash', 'swimming', 'gym', 'running', 'yoga', 'golf', 'boxing',
];

void main() {
  test('all 15 sport icons exist as individual assets and resolve from icon_key and slug', () {
    for (final key in fifteen) {
      expect(File('assets/icons/sports/$key.png').existsSync(), isTrue, reason: key);
      expect(sportIconAsset(key), 'assets/icons/sports/$key.png');
    }
    expect(sportIconAsset(null, slug: 'table-tennis'), 'assets/icons/sports/table_tennis.png');
    expect(sportIconAsset('snooker'), isNull); // no branded icon: Material fallback is used
  });

  testWidgets('home category cards show the branded sport icons', (tester) async {
    final env = TestEnv();
    await env.pump(tester);
    final assets = tester
        .widgetList<Image>(find.byType(Image))
        .map((i) => i.image)
        .whereType<AssetImage>()
        .map((i) => i.assetName)
        .toSet();
    // the fake catalogue has badminton, tennis and swimming
    expect(assets, containsAll(['assets/icons/sports/badminton.png', 'assets/icons/sports/tennis.png', 'assets/icons/sports/swimming.png']));
  });
}
