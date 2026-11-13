import 'package:flutter_shared/flutter_shared.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:zuruv/core/router/app_router.dart';
import 'package:zuruv/customer/shared/models/app_notification.dart';

import 'helpers.dart';

AppNotification note(String id, {bool read = false, String? bookingId = 'b1', String type = 'booking.confirmed'}) =>
    AppNotification(
      id: id,
      type: type,
      title: 'Booking confirmed',
      body: 'Ace Arena',
      isRead: read,
      createdAt: DateTime.utc(2030, 1, 1, 10),
      bookingId: bookingId,
    );

void main() {
  Future<TestEnv> openNotifications(WidgetTester tester, FakeNotificationRepository repo) async {
    final env = TestEnv(
      notifications: repo,
      bookings: FakeBookingRepository(bookings: [bookingOf('b1', status: 'confirmed', paymentStatus: 'paid')]),
    );
    await env.pump(tester);
    await tester.tap(find.byTooltip('Notifications'));
    await tester.pumpAndSettle();
    return env;
  }

  testWidgets('empty state', (tester) async {
    await openNotifications(tester, FakeNotificationRepository());
    expect(find.text('Nothing here yet'), findsOneWidget);
  });

  testWidgets('lists notifications; tapping marks it read and opens the booking', (tester) async {
    final repo = FakeNotificationRepository()..items = [note('n1'), note('n2', read: true)];
    await openNotifications(tester, repo);
    expect(find.text('Booking confirmed'), findsNWidgets(2));
    expect(find.text('Mark all read'), findsOneWidget);
    await tester.tap(find.text('Booking confirmed').first);
    await tester.pumpAndSettle();
    expect(repo.read, ['n1']);
    expect(find.text('Booking details'), findsOneWidget);
  });

  testWidgets('mark all read', (tester) async {
    final repo = FakeNotificationRepository()..items = [note('n1'), note('n2')];
    await openNotifications(tester, repo);
    await tester.tap(find.text('Mark all read'));
    await tester.pumpAndSettle();
    expect(repo.readAll, 1);
    expect(find.text('Mark all read'), findsNothing);
  });

  testWidgets('load failure offers retry', (tester) async {
    final repo = FakeNotificationRepository()..listError = const ApiException(statusCode: 0, code: 'NETWORK', message: 'x');
    await openNotifications(tester, repo);
    expect(find.textContaining('Cannot reach the server'), findsOneWidget);
  });

  test('a tapped push opens the related booking, or the notification list', () {
    expect(pushRoute({'booking_id': 'b9', 'type': 'booking.confirmed'}, AppRole.customer), '/bookings/b9');
    expect(pushRoute({'type': 'payment.failed'}, AppRole.customer), '/notifications');
    expect(pushRoute({'booking_id': ''}, AppRole.customer), '/notifications');
  });
}
