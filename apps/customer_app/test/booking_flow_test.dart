import 'package:flutter/material.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:zuruv_customer/shared/models/booking.dart';

import 'helpers.dart';
import 'venue_details_test.dart' show detail;

void main() {
  Future<TestEnv> openBooking(WidgetTester tester, {FakeBookingRepository? bookings}) async {
    final env = TestEnv(
      venues: FakeVenueRepository(details: {'v1': detail()}),
      bookings: bookings ?? FakeBookingRepository(),
    );
    await env.pump(tester);
    await tester.tap(find.text('Ace Arena').first);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Book Now'));
    await tester.pumpAndSettle();
    return env;
  }

  Future<void> pickFirstSlot(WidgetTester tester) async {
    await tester.tap(find.text('09:00'));
    await tester.pumpAndSettle();
  }

  testWidgets('shows only the slots the server returned, with the court price', (tester) async {
    await openBooking(tester);
    expect(find.text('09:00'), findsOneWidget);
    expect(find.text('10:00'), findsOneWidget);
    expect(find.text('11:00'), findsNothing);
    expect(find.textContaining('₹500'), findsWidgets);
    expect(find.text('Select a slot'), findsOneWidget);
    expect(tester.widget<FilledButton>(find.widgetWithText(FilledButton, 'Review & book')).onPressed, isNull);
  });

  testWidgets('picking another date asks the server again', (tester) async {
    final repo = FakeBookingRepository();
    await openBooking(tester, bookings: repo);
    final before = repo.availabilityDates.length;
    await tester.tap(find.byType(InkWell).at(1)); // second day in the strip
    await tester.pumpAndSettle();
    expect(repo.availabilityDates.length, before + 1);
    expect(repo.availabilityDates.last, isNot(repo.availabilityDates.first));
  });

  testWidgets('closed day and venue without courts show clear messages', (tester) async {
    await openBooking(tester, bookings: FakeBookingRepository(closedReason: 'special_closure', note: 'Holi', courts: [
      const CourtAvailability(resourceId: 'r1', name: 'Court 1', state: ResourceState.closed, slots: [], message: 'Holi'),
    ]));
    expect(find.text('Holi'), findsWidgets);
    expect(find.byType(ChoiceChip), findsNothing);
  });

  testWidgets('no courts configured explains that booking is not open', (tester) async {
    await openBooking(tester, bookings: FakeBookingRepository(courts: const []));
    expect(find.text('Not open for booking yet'), findsOneWidget);
  });

  testWidgets('availability failure shows an error with retry', (tester) async {
    final repo = FakeBookingRepository()..availabilityError = const ApiException(statusCode: 0, code: 'NETWORK', message: 'x');
    await openBooking(tester, bookings: repo);
    expect(find.textContaining('Cannot reach the server'), findsOneWidget);
    repo.availabilityError = null;
    await tester.tap(find.text('Try again'));
    await tester.pumpAndSettle();
    expect(find.text('09:00'), findsOneWidget);
  });

  testWidgets('select a slot, review the server price, confirm, land on the booking', (tester) async {
    final repo = FakeBookingRepository();
    await openBooking(tester, bookings: repo);
    await pickFirstSlot(tester);
    expect(find.textContaining('Court 1 · 09:00–10:00'), findsOneWidget);
    await tester.tap(find.text('Review & book'));
    await tester.pumpAndSettle();
    expect(find.text('Review your booking'), findsOneWidget);
    expect(find.text('Total'), findsOneWidget);
    expect(find.textContaining('confirmed only after your payment is verified'), findsOneWidget);
    await tester.tap(find.text('Continue to payment'));
    await tester.pumpAndSettle();
    expect(repo.idempotencyKeys.length, 1);
    expect(repo.idempotencyKeys.single.length, greaterThanOrEqualTo(8));
    // A held booking goes straight to the payment screen, never to a "confirmed" state.
    expect(find.text('Payment'), findsWidgets);
    expect(find.text('Booking ZUR-ABCD2345'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, 'Pay ₹500'), findsOneWidget);
    expect(find.text('Payment successful'), findsNothing);
  });

  testWidgets('a slot taken meanwhile is reported and availability is reloaded', (tester) async {
    final repo = FakeBookingRepository();
    await openBooking(tester, bookings: repo);
    await pickFirstSlot(tester);
    repo.quoteError = const ApiException(statusCode: 409, code: 'SLOT_UNAVAILABLE', message: 'taken');
    final loads = repo.availabilityDates.length;
    await tester.tap(find.text('Review & book'));
    await tester.pumpAndSettle();
    expect(find.textContaining('no longer available'), findsOneWidget);
    expect(repo.availabilityDates.length, loads + 1);
    expect(find.text('Select a slot'), findsOneWidget); // selection cleared
  });

  testWidgets('conflict on create also reloads availability', (tester) async {
    final repo = FakeBookingRepository();
    await openBooking(tester, bookings: repo);
    await pickFirstSlot(tester);
    await tester.tap(find.text('Review & book'));
    await tester.pumpAndSettle();
    repo.createError = const ApiException(statusCode: 409, code: 'SLOT_UNAVAILABLE', message: 'taken');
    await tester.tap(find.text('Continue to payment'));
    await tester.pumpAndSettle();
    expect(find.textContaining('no longer available'), findsOneWidget);
    expect(find.text('Review your booking'), findsNothing);
  });

  testWidgets('a network failure keeps the sheet open and retries with the SAME idempotency key', (tester) async {
    final repo = FakeBookingRepository();
    await openBooking(tester, bookings: repo);
    await pickFirstSlot(tester);
    await tester.tap(find.text('Review & book'));
    await tester.pumpAndSettle();
    repo.createError = const ApiException(statusCode: 0, code: 'NETWORK', message: 'offline');
    await tester.tap(find.text('Continue to payment'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Cannot reach the server'), findsOneWidget);
    repo.createError = null;
    await tester.tap(find.text('Try again'));
    await tester.pumpAndSettle();
    expect(repo.idempotencyKeys.length, 2);
    expect(repo.idempotencyKeys[0], repo.idempotencyKeys[1]);
    expect(find.widgetWithText(FilledButton, 'Pay ₹500'), findsOneWidget);
  });

  testWidgets('a server rejection is shown and no booking appears', (tester) async {
    final repo = FakeBookingRepository();
    await openBooking(tester, bookings: repo);
    await pickFirstSlot(tester);
    await tester.tap(find.text('Review & book'));
    await tester.pumpAndSettle();
    repo.createError = const ApiException(statusCode: 503, code: 'BOOKING_NOT_CONFIGURED', message: 'Online booking is not configured yet.');
    await tester.tap(find.text('Continue to payment'));
    await tester.pumpAndSettle();
    expect(find.text('Online booking is not configured yet.'), findsOneWidget);
    expect(repo.bookings, isEmpty);
  });

  group('My Bookings', () {
    Future<TestEnv> openList(WidgetTester tester, FakeBookingRepository repo) async {
      final env = TestEnv(bookings: repo);
      await env.pump(tester);
      await tester.tap(inNavBar('Bookings'));
      await tester.pumpAndSettle();
      return env;
    }

    testWidgets('empty states per tab', (tester) async {
      await openList(tester, FakeBookingRepository());
      expect(find.text('No upcoming bookings'), findsOneWidget);
      await tester.tap(find.text('Past'));
      await tester.pumpAndSettle();
      expect(find.text('No past bookings'), findsOneWidget);
      await tester.tap(find.text('Cancelled'));
      await tester.pumpAndSettle();
      expect(find.text('No cancelled bookings'), findsOneWidget);
    });

    testWidgets('lists bookings in the right tab with status', (tester) async {
      final repo = FakeBookingRepository(bookings: [
        bookingOf('b1', status: 'confirmed'),
        bookingOf('b2', status: 'completed', venueName: 'Old Club'),
        bookingOf('b3', status: 'cancelled_by_customer', venueName: 'Gone Club'),
      ]);
      await openList(tester, repo);
      expect(find.text('Ace Arena'), findsOneWidget);
      expect(find.text('Confirmed'), findsOneWidget);
      expect(find.text('Old Club'), findsNothing);
      await tester.tap(find.text('Past'));
      await tester.pumpAndSettle();
      expect(find.text('Old Club'), findsOneWidget);
      await tester.tap(find.text('Cancelled'));
      await tester.pumpAndSettle();
      expect(find.text('Gone Club'), findsOneWidget);
    });

    testWidgets('load failure offers retry', (tester) async {
      final repo = FakeBookingRepository(bookings: [bookingOf('b1', status: 'confirmed')])
        ..listError = const ApiException(statusCode: 0, code: 'NETWORK', message: 'x');
      await openList(tester, repo);
      expect(find.textContaining('Cannot reach the server'), findsOneWidget);
      repo.listError = null;
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('Ace Arena'), findsOneWidget);
    });

    testWidgets('cancel flow asks the server first, then cancels', (tester) async {
      final repo = FakeBookingRepository(bookings: [bookingOf('b1', history: [
        StatusEvent(toStatus: 'pending_payment', actorRole: 'customer', createdAt: DateTime.utc(2030, 1, 1)),
      ])]);
      await openList(tester, repo);
      await tester.tap(find.text('Ace Arena'));
      await tester.pumpAndSettle();
      expect(find.text('Booking details'), findsOneWidget);
      expect(find.text('History'), findsOneWidget);
      await tester.tap(find.widgetWithText(OutlinedButton, 'Cancel booking'));
      await tester.pumpAndSettle();
      expect(find.text('Cancel this booking?'), findsOneWidget);
      await tester.tap(find.widgetWithText(FilledButton, 'Cancel booking'));
      await tester.pumpAndSettle();
      expect(repo.cancelled, ['b1']);
      expect(find.text('Cancelled'), findsWidgets);
      expect(find.widgetWithText(OutlinedButton, 'Cancel booking'), findsNothing);
    });

    testWidgets('when the server says cancellation is not allowed, the reason is shown', (tester) async {
      final repo = FakeBookingRepository(bookings: [bookingOf('b1', status: 'confirmed')])
        ..preview = const CancellationPreview(
          canCancel: false,
          code: 'CANCELLATION_WINDOW_CLOSED',
          message: 'Bookings can be cancelled at least 24 hour(s) before the start.',
        );
      await openList(tester, repo);
      await tester.tap(find.text('Ace Arena'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(OutlinedButton, 'Cancel booking'));
      await tester.pumpAndSettle();
      expect(find.text('Cannot cancel'), findsOneWidget);
      expect(find.textContaining('at least 24 hour'), findsOneWidget);
      expect(repo.cancelled, isEmpty);
    });

    testWidgets('a booking with can_cancel=false has no cancel button', (tester) async {
      final repo = FakeBookingRepository(bookings: [bookingOf('b1', status: 'confirmed', canCancel: false)]);
      await openList(tester, repo);
      await tester.tap(find.text('Ace Arena'));
      await tester.pumpAndSettle();
      expect(find.widgetWithText(OutlinedButton, 'Cancel booking'), findsNothing);
    });
  });
}
