import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:zuruv_customer/features/payments/checkout_launcher.dart';

import 'helpers.dart';

void main() {
  const apiOffline = ApiException(statusCode: 0, code: 'NETWORK', message: 'offline');

  /// Opens My Bookings -> the held booking -> the Payment screen.
  Future<TestEnv> openPayment(
    WidgetTester tester, {
    FakePaymentRepository? payments,
    FakeCheckoutLauncher? checkout,
    String status = 'pending_payment',
  }) async {
    final env = TestEnv(
      bookings: FakeBookingRepository(bookings: [bookingOf('b1', status: status)]),
      payments: payments,
      checkout: checkout,
    );
    await env.pump(tester);
    await tester.tap(inNavBar('Bookings'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Ace Arena'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Pay ₹500'));
    await tester.pumpAndSettle();
    return env;
  }

  Future<void> pay(WidgetTester tester) async {
    await tester.tap(find.widgetWithText(FilledButton, 'Pay ₹500'));
    await tester.pumpAndSettle();
  }

  testWidgets('the booking details no longer claim payment is unavailable and offer to pay', (tester) async {
    final env = TestEnv(bookings: FakeBookingRepository(bookings: [bookingOf('b1')]));
    await env.pump(tester);
    await tester.tap(inNavBar('Bookings'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Ace Arena'));
    await tester.pumpAndSettle();
    expect(find.textContaining('not available yet'), findsNothing);
    expect(find.textContaining('Complete the payment'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, 'Pay ₹500'), findsOneWidget);
  });

  testWidgets('the payment screen shows the booking summary and the amount from the server', (tester) async {
    await openPayment(tester);
    expect(find.text('Amount to pay'), findsOneWidget);
    expect(find.text('Secure payment'), findsOneWidget);
    expect(find.text('Payment successful'), findsNothing);
  });

  testWidgets('verified success: order created for the booking id only, signature sent to the backend, then confirmed',
      (tester) async {
    final payments = FakePaymentRepository();
    final env = await openPayment(tester, payments: payments);
    await pay(tester);
    expect(payments.orders, ['b1']);
    expect(env.checkout.opened.single.keyId, 'rzp_test_fake');
    expect(payments.verifies.single.signature, 'sig_1');
    expect(payments.verifies.single.paymentId, 'pay_1');
    expect(find.text('Payment successful'), findsOneWidget);
    expect(find.text('Your booking is confirmed.'), findsOneWidget);
  });

  testWidgets('a checkout "success" that the backend has NOT confirmed is never shown as success', (tester) async {
    final payments = FakePaymentRepository()
      ..verifyResult = paymentOf(status: 'pending') // backend: not captured yet
      ..getResults = [paymentOf(status: 'pending')]; // still undecided while polling
    await openPayment(tester, payments: payments);
    await pay(tester);
    expect(find.text('Payment pending'), findsOneWidget);
    expect(find.text('Payment successful'), findsNothing);
    expect(find.text('Your booking is confirmed.'), findsNothing);
    expect(payments.gets, greaterThan(0));
  });

  testWidgets('delayed confirmation: pending first, then confirmed by the server record', (tester) async {
    final payments = FakePaymentRepository()
      ..verifyResult = paymentOf(status: 'pending')
      ..getResults = [paymentOf(status: 'pending'), confirmedPayment()];
    await openPayment(tester, payments: payments);
    await pay(tester);
    expect(find.text('Payment successful'), findsOneWidget);
  });

  testWidgets('"Verification in progress" is shown while the backend verifies', (tester) async {
    final gate = Completer<void>();
    final payments = FakePaymentRepository()..verifyGate = gate;
    await openPayment(tester, payments: payments);
    await tester.tap(find.widgetWithText(FilledButton, 'Pay ₹500'));
    await tester.pump();
    await tester.pump();
    await tester.pump();
    expect(find.text('Verification in progress'), findsOneWidget);
    expect(find.text('Payment successful'), findsNothing);
    gate.complete();
    await tester.pumpAndSettle();
    expect(find.text('Payment successful'), findsOneWidget);
  });

  testWidgets('payment failure: nothing is confirmed and Try again re-uses the flow', (tester) async {
    final payments = FakePaymentRepository();
    final checkout = FakeCheckoutLauncher([const CheckoutFailure('Payment failed at bank'), okCheckout()]);
    await openPayment(tester, payments: payments, checkout: checkout);
    await pay(tester);
    expect(find.text('Payment failed'), findsOneWidget);
    expect(find.text('Payment failed at bank'), findsOneWidget);
    expect(find.text('Payment successful'), findsNothing);
    expect(payments.verifies, isEmpty);
    await tester.tap(find.widgetWithText(FilledButton, 'Try again'));
    await tester.pumpAndSettle();
    expect(payments.orders, ['b1', 'b1']); // the server reuses the same order
    expect(find.text('Payment successful'), findsOneWidget);
  });

  testWidgets('closing checkout is a cancellation, not a failure, and can be retried', (tester) async {
    final checkout = FakeCheckoutLauncher([const CheckoutCancelled(), okCheckout()]);
    final payments = FakePaymentRepository();
    await openPayment(tester, payments: payments, checkout: checkout);
    await pay(tester);
    expect(find.text('Payment cancelled'), findsOneWidget);
    expect(payments.verifies, isEmpty);
    await tester.tap(find.widgetWithText(FilledButton, 'Try again'));
    await tester.pumpAndSettle();
    expect(find.text('Payment successful'), findsOneWidget);
  });

  testWidgets('network drop inside checkout: the app asks the server instead of guessing', (tester) async {
    final payments = FakePaymentRepository()..getResults = [paymentOf(status: 'pending'), confirmedPayment()];
    await openPayment(tester, payments: payments, checkout: FakeCheckoutLauncher([const CheckoutNetworkError()]));
    await pay(tester);
    expect(payments.verifies, isEmpty);
    expect(find.text('Payment successful'), findsOneWidget);
  });

  testWidgets('network failure while verifying keeps the result and retries verification, not payment', (tester) async {
    final payments = FakePaymentRepository()..verifyError = apiOffline;
    await openPayment(tester, payments: payments);
    await pay(tester);
    expect(find.text('No connection'), findsOneWidget);
    expect(find.text('Payment successful'), findsNothing);
    await tester.tap(find.widgetWithText(FilledButton, 'Try again'));
    await tester.pumpAndSettle();
    expect(payments.orders.length, 1); // no second order, no second checkout
    expect(payments.verifies.length, 2);
    expect(payments.verifies[0].signature, payments.verifies[1].signature);
    expect(find.text('Payment successful'), findsOneWidget);
  });

  testWidgets('an invalid signature is reported as a failed payment', (tester) async {
    final payments = FakePaymentRepository()
      ..verifyError = const ApiException(statusCode: 400, code: 'PAYMENT_SIGNATURE_INVALID', message: 'Payment verification failed.');
    await openPayment(tester, payments: payments);
    await pay(tester);
    expect(find.text('Payment failed'), findsOneWidget);
    expect(find.text('Payment successful'), findsNothing);
  });

  testWidgets('an expired hold cannot be paid and offers to book again', (tester) async {
    final payments = FakePaymentRepository()
      ..createError = const ApiException(statusCode: 409, code: 'HOLD_EXPIRED', message: 'Payment time ran out.');
    final env = await openPayment(tester, payments: payments);
    await pay(tester);
    expect(find.text('Time ran out'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, 'Book again'), findsOneWidget);
    expect(env.checkout.opened, isEmpty);
  });

  testWidgets('order creation offline lets the user retry', (tester) async {
    final payments = FakePaymentRepository()..createError = apiOffline;
    await openPayment(tester, payments: payments);
    await pay(tester);
    expect(find.text('No connection'), findsOneWidget);
    payments.createError = null;
    await tester.tap(find.widgetWithText(FilledButton, 'Try again'));
    await tester.pumpAndSettle();
    expect(find.text('Payment successful'), findsOneWidget);
  });

  testWidgets('money taken but booking not confirmable is explained, not shown as confirmed', (tester) async {
    final payments = FakePaymentRepository()
      ..verifyResult = paymentOf(status: 'captured', needsReview: true, bookingStatus: 'expired');
    await openPayment(tester, payments: payments);
    await pay(tester);
    expect(find.text('Payment received'), findsOneWidget);
    expect(find.textContaining('could not confirm the booking'), findsOneWidget);
    expect(find.text('Payment successful'), findsNothing);
  });

  testWidgets('double tapping Pay opens checkout once', (tester) async {
    final gate = Completer<void>();
    final payments = FakePaymentRepository()..verifyGate = gate;
    final env = await openPayment(tester, payments: payments);
    final button = find.widgetWithText(FilledButton, 'Pay ₹500');
    await tester.tap(button);
    await tester.pump();
    await tester.tap(button, warnIfMissed: false);
    await tester.pump();
    gate.complete();
    await tester.pumpAndSettle();
    expect(env.checkout.opened.length, 1);
    expect(payments.orders.length, 1);
  });

  testWidgets('an already-paid booking shows success without asking to pay again', (tester) async {
    final env = TestEnv(
      bookings: FakeBookingRepository(bookings: [bookingOf('b1', status: 'confirmed', paymentStatus: 'paid')]),
    );
    await env.pump(tester);
    await tester.tap(inNavBar('Bookings'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Ace Arena'));
    await tester.pumpAndSettle();
    expect(find.text('Paid'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, 'Pay ₹500'), findsNothing);
  });

  group('payment history', () {
    Future<TestEnv> openHistory(WidgetTester tester, FakePaymentRepository payments) async {
      final env = TestEnv(payments: payments);
      await env.pump(tester);
      await tester.tap(inNavBar('Profile'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Payment history'));
      await tester.pumpAndSettle();
      return env;
    }

    testWidgets('empty state', (tester) async {
      await openHistory(tester, FakePaymentRepository());
      expect(find.text('No payments yet'), findsOneWidget);
    });

    testWidgets('lists real payment records with their status', (tester) async {
      await openHistory(
        tester,
        FakePaymentRepository()
          ..historyItems = [
            confirmedPayment(),
            paymentOf(id: 'p2', bookingId: 'b2', status: 'failed', failureReason: 'x'),
          ],
      );
      expect(find.text('Paid'), findsOneWidget);
      expect(find.text('Failed'), findsOneWidget);
      expect(find.text('₹500'), findsWidgets);
    });

    testWidgets('a load failure offers retry', (tester) async {
      final payments = FakePaymentRepository()..historyError = apiOffline;
      await openHistory(tester, payments);
      expect(find.textContaining('Cannot reach the server'), findsOneWidget);
      payments.historyError = null;
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('No payments yet'), findsOneWidget);
    });
  });
}
