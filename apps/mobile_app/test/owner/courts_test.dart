import 'package:flutter/material.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:zuruv/owner/shared/models/models.dart';

import 'helpers.dart';

const conflict = ApiException(
  statusCode: 409,
  code: 'SCHEDULE_CONFLICT',
  message: 'This change would affect existing bookings. Nothing was changed.',
  details: {
    'count': 2,
    'bookings': [
      {'booking_code': 'ZUR-AAAA1111'},
      {'booking_code': 'ZUR-BBBB2222'},
    ],
  },
);

Future<void> openCourts(WidgetTester tester, TestEnv env) async {
  await env.pump(tester);
  await tester.tap(inNavBar('Venues'));
  await tester.pumpAndSettle();
  await tester.tap(find.text('Ace Arena'));
  await tester.pumpAndSettle();
  await tester.scrollUntilVisible(find.text('Courts & blocked times'), 200, scrollable: find.byType(Scrollable).last);
  await tester.tap(find.text('Courts & blocked times'));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('empty state explains that a court needs a slot length and price', (tester) async {
    await openCourts(tester, TestEnv());
    expect(find.text('No courts yet'), findsOneWidget);
    expect(find.text('Nothing blocked'), findsOneWidget);
  });

  testWidgets('add a court with slot length and price', (tester) async {
    final repo = FakeOwnerRepository();
    await openCourts(tester, TestEnv(repo: repo));
    await tester.tap(find.text('Add court'));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextField, 'Court name'), 'Court 1');
    await tester.enterText(find.widgetWithText(TextField, 'Slot length (minutes)'), '60');
    await tester.enterText(find.widgetWithText(TextField, 'Price per slot (₹)'), '500');
    await tester.tap(find.text('Save court'));
    await tester.pumpAndSettle();
    expect(repo.savedCourts.single['slot_minutes'], 60);
    expect(repo.savedCourts.single['slot_price_paise'], 50000); // price is sent in paise
    expect(find.text('Court 1'), findsOneWidget);
    expect(find.textContaining('60 min slots'), findsOneWidget);
  });

  testWidgets('court form validates before calling the server', (tester) async {
    final repo = FakeOwnerRepository();
    await openCourts(tester, TestEnv(repo: repo));
    await tester.tap(find.text('Add court'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Save court'));
    await tester.pumpAndSettle();
    expect(find.text('Enter a court name.'), findsOneWidget);
    await tester.enterText(find.widgetWithText(TextField, 'Court name'), 'Court 1');
    await tester.enterText(find.widgetWithText(TextField, 'Slot length (minutes)'), '2');
    await tester.tap(find.text('Save court'));
    await tester.pumpAndSettle();
    expect(find.textContaining('between 5 and 720'), findsOneWidget);
    expect(repo.savedCourts, isEmpty);
  });

  testWidgets('a court without slot length or price is shown as not open for booking', (tester) async {
    final repo = FakeOwnerRepository();
    repo.courtList['v1'] = const [Court(id: 'c1', name: 'Spare', isActive: true)];
    await openCourts(tester, TestEnv(repo: repo));
    expect(find.textContaining('Not open for booking'), findsOneWidget);
  });

  testWidgets('a change that would break bookings is refused and the bookings are named', (tester) async {
    final repo = FakeOwnerRepository();
    repo.courtList['v1'] = const [Court(id: 'c1', name: 'Court 1', isActive: true, slotMinutes: 60, slotPricePaise: 50000)];
    repo.saveCourtError = conflict;
    await openCourts(tester, TestEnv(repo: repo));
    await tester.tap(find.text('Court 1'));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextField, 'Slot length (minutes)'), '45');
    await tester.tap(find.text('Save court'));
    await tester.pumpAndSettle();
    expect(find.textContaining('would affect 2 existing bookings'), findsOneWidget);
    expect(find.textContaining('ZUR-AAAA1111'), findsOneWidget);
    expect(find.textContaining('60 min slots'), findsOneWidget); // unchanged on screen
  });

  testWidgets('blocked times list, remove, and incomplete form is rejected locally', (tester) async {
    final repo = FakeOwnerRepository();
    repo.blockList['v1'] = [TimeBlock(id: 'blk1', startsAt: DateTime(2030, 1, 7, 12), endsAt: DateTime(2030, 1, 7, 14), reason: 'Maintenance')];
    await openCourts(tester, TestEnv(repo: repo));
    expect(find.text('Whole venue'), findsOneWidget);
    expect(find.textContaining('Maintenance'), findsOneWidget);
    await tester.tap(find.byTooltip('Remove block'));
    await tester.pumpAndSettle();
    expect(repo.deletedBlocks, ['blk1']);
    expect(find.text('Nothing blocked'), findsOneWidget);

    await tester.scrollUntilVisible(find.text('Block a time'), 200, scrollable: find.byType(Scrollable).last);
    await tester.tap(find.text('Block a time'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Block time'));
    await tester.pumpAndSettle();
    expect(find.text('Choose a date, start and end time.'), findsOneWidget);
  });

  testWidgets('saving hours that would break bookings shows the refusal', (tester) async {
    final repo = FakeOwnerRepository()..saveScheduleError = conflict;
    await openCourts(tester, TestEnv(repo: repo));
    await tester.pageBack();
    await tester.pumpAndSettle();
    await tester.tap(find.text('Manage slots & hours'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('open-0')));
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.text('Save weekly hours'), 300, scrollable: find.byType(Scrollable).last);
    await tester.tap(find.text('Save weekly hours'));
    await tester.pumpAndSettle();
    expect(find.textContaining('would affect 2 existing bookings'), findsOneWidget);
  });
}
