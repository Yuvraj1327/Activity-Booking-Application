import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:zuruv_owner/shared/models/models.dart';

import 'helpers.dart';

Future<void> openSlots(WidgetTester tester, TestEnv env) async {
  await env.pump(tester);
  await tester.tap(inNavBar('Venues'));
  await tester.pumpAndSettle();
  await tester.tap(find.text('Ace Arena'));
  await tester.pumpAndSettle();
  await tester.tap(find.text('Manage slots & hours'));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('shows seven days, an honest note about slot configuration, and saves weekly hours', (tester) async {
    final repo = FakeOwnerRepository();
    await openSlots(tester, TestEnv(repo: repo));
    expect(find.text('Monday'), findsOneWidget);
    expect(find.text('No bookable courts yet'), findsOneWidget);

    await tester.tap(find.byKey(const ValueKey('open-0')));
    await tester.pumpAndSettle();
    expect(find.text('6:00 AM'), findsOneWidget);
    expect(find.text('10:00 PM'), findsOneWidget);

    await tester.scrollUntilVisible(find.text('Save weekly hours'), 300, scrollable: find.byType(Scrollable).last);
    await tester.tap(find.text('Save weekly hours'));
    await tester.pumpAndSettle();
    expect(repo.savedRegular, isNotNull);
    expect(repo.savedRegular!.length, 7);
    expect(repo.savedRegular!.first.intervals.single, const TimeInterval('06:00', '22:00'));
    expect(repo.savedRegular![1].isOpen, isFalse);
  });

  testWidgets('special dates: add a closure, remove it, save', (tester) async {
    final repo = FakeOwnerRepository();
    repo.special = const [SpecialDate(onDate: '2030-01-26', isClosed: true, note: 'Holiday')];
    await openSlots(tester, TestEnv(repo: repo));
    await tester.tap(find.text('Special dates'));
    await tester.pumpAndSettle();
    expect(find.text('26 Jan 2030'), findsOneWidget);
    expect(find.textContaining('Closed'), findsWidgets);

    await tester.tap(find.byTooltip('Remove'));
    await tester.pumpAndSettle();
    expect(find.text('No special dates'), findsOneWidget);

    await tester.tap(find.text('Save special dates'));
    await tester.pumpAndSettle();
    expect(repo.savedSpecial, isEmpty);
  });
}
