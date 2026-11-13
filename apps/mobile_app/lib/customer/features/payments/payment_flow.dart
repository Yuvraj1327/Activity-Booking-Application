import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';

import 'package:zuruv/customer/shared/models/payment.dart';
import 'package:zuruv/customer/shared/repositories/payment_repository.dart';
import 'package:zuruv/customer/features/booking/booking_providers.dart';
import 'package:zuruv/customer/features/payments/checkout_launcher.dart';

/// Where the payment is. Only [success] means the BACKEND confirmed payment and booking.
enum PayPhase {
  idle,
  creatingOrder, // "Processing"
  checkout, // Razorpay sheet is open
  verifying, // "Verification in progress"
  pending, // "Payment pending": checked with the server, not confirmed yet
  success, // "Payment successful": backend says confirmed
  failed, // "Payment failed": retry is offered
  cancelled, // customer closed checkout: retry is offered
  expired, // the hold ran out: book again
  needsReview, // money taken, booking could not be confirmed
  offline, // network problem talking to OUR server: retry is safe
  error,
}

class PayState {
  const PayState({this.phase = PayPhase.idle, this.message, this.payment});

  final PayPhase phase;
  final String? message;
  final PaymentInfo? payment;

  bool get busy =>
      phase == PayPhase.creatingOrder || phase == PayPhase.checkout || phase == PayPhase.verifying;
}

/// How often / how long to ask the server while a payment is still being confirmed.
class PollConfig {
  const PollConfig({this.interval = const Duration(seconds: 3), this.attempts = 10});

  final Duration interval;
  final int attempts;
}

final pollConfigProvider = Provider<PollConfig>((ref) => const PollConfig());

/// Drives one booking's payment: create order -> Razorpay Checkout -> backend verification ->
/// (poll if the confirmation is delayed). Retries reuse the same order on the server, so tapping
/// "Pay" twice or after a failure can never create a second payment.
class PaymentFlowController extends AutoDisposeFamilyNotifier<PayState, String> {
  CheckoutSuccess? _unverified; // a checkout result the server has not acknowledged yet
  String? _paymentId;
  bool _disposed = false;

  @override
  PayState build(String bookingId) {
    ref.onDispose(() => _disposed = true);
    return const PayState();
  }

  PaymentRepository get _repo => ref.read(paymentRepositoryProvider);

  void _set(PayState s) {
    if (!_disposed) state = s;
  }

  Future<void> start() async {
    if (state.busy) return; // ignore double taps
    // If a checkout result is still waiting for the server, finish that instead of paying again.
    if (_unverified != null && _paymentId != null) return retryVerification();
    _set(const PayState(phase: PayPhase.creatingOrder));
    final CreateOrderResult order;
    try {
      order = await _repo.createOrder(arg);
    } on ApiException catch (e) {
      _set(_fromCreateError(e));
      return;
    } catch (_) {
      _set(const PayState(phase: PayPhase.error, message: 'Something went wrong. Please try again.'));
      return;
    }
    _paymentId = order.payment.id;
    _set(PayState(phase: PayPhase.checkout, payment: order.payment));
    final result = await ref.read(checkoutLauncherProvider).open(order.checkout);
    switch (result) {
      case CheckoutSuccess():
        _unverified = result;
        await _verify(result);
      case CheckoutFailure(:final message):
        _set(PayState(phase: PayPhase.failed, message: message, payment: order.payment));
        // The webhook may still report something different; look once without blocking the user.
        await _look(order.payment.id, quiet: true);
      case CheckoutCancelled():
        _set(PayState(phase: PayPhase.cancelled, payment: order.payment));
      case CheckoutNetworkError():
        // The payment may have gone through even though the device lost connection.
        await _poll(order.payment.id);
    }
  }

  PayState _fromCreateError(ApiException e) {
    if (e.isNetworkError) {
      return const PayState(
        phase: PayPhase.offline,
        message: 'Cannot reach the server. Check your connection and try again.',
      );
    }
    return switch (e.code) {
      'HOLD_EXPIRED' || 'BOOKING_NOT_PAYABLE' => PayState(phase: PayPhase.expired, message: e.message),
      'ALREADY_PAID' => const PayState(phase: PayPhase.pending, message: 'This booking is already paid.'),
      _ => PayState(phase: PayPhase.error, message: e.message),
    };
  }

  Future<void> retryVerification() async {
    final s = _unverified;
    if (s == null || state.busy) return;
    await _verify(s);
  }

  Future<void> _verify(CheckoutSuccess s) async {
    final id = _paymentId!;
    _set(PayState(phase: PayPhase.verifying, payment: state.payment));
    try {
      final p = await _repo.verify(orderId: s.orderId, paymentId: s.paymentId, signature: s.signature);
      _unverified = null;
      await _settle(p);
    } on ApiException catch (e) {
      if (e.isNetworkError) {
        // Keep the checkout result so "Try again" re-sends the same verification.
        _set(PayState(
          phase: PayPhase.offline,
          message: 'Payment received by the gateway. Reconnect so we can confirm it.',
          payment: state.payment,
        ));
      } else if (e.code == 'PAYMENT_SIGNATURE_INVALID') {
        _unverified = null;
        _set(PayState(phase: PayPhase.failed, message: 'The payment could not be verified.', payment: state.payment));
      } else {
        _unverified = null;
        await _poll(id); // the server could not decide right now: check its record
      }
    }
  }

  /// Turns the server's answer into a screen state. Success requires `confirmed == true`.
  Future<void> _settle(PaymentInfo p) async {
    if (p.confirmed) {
      ref.read(bookingsRevisionProvider.notifier).state++;
      ref.invalidate(bookingDetailProvider(arg));
      _set(PayState(phase: PayPhase.success, payment: p));
    } else if (p.needsReview) {
      ref.invalidate(bookingDetailProvider(arg));
      _set(PayState(
        phase: PayPhase.needsReview,
        message: 'We received your payment but could not confirm the booking. Our team will review it.',
        payment: p,
      ));
    } else if (p.isFailed) {
      _set(PayState(phase: PayPhase.failed, message: p.failureReason ?? 'The payment did not go through.', payment: p));
    } else if (p.bookingStatus == 'expired') {
      _set(PayState(phase: PayPhase.expired, message: 'The payment time for this booking ran out.', payment: p));
    } else {
      await _poll(p.id, first: p);
    }
  }

  /// Polls the server record while confirmation is delayed. Ends in [PayPhase.pending] if it is
  /// still undecided: the webhook will confirm later and "Check again" re-asks.
  Future<void> _poll(String paymentId, {PaymentInfo? first}) async {
    final cfg = ref.read(pollConfigProvider);
    _set(PayState(phase: PayPhase.pending, payment: first ?? state.payment));
    for (var i = 0; i < cfg.attempts && !_disposed; i++) {
      await Future<void>.delayed(cfg.interval);
      if (_disposed) return;
      try {
        final p = await _repo.get(paymentId);
        if (p.confirmed || p.needsReview || p.isFailed || p.bookingStatus == 'expired') {
          await _settle(p);
          return;
        }
        _set(PayState(phase: PayPhase.pending, payment: p));
      } catch (_) {
        // Network blip: keep polling; the state stays "pending".
      }
    }
    _set(PayState(
      phase: PayPhase.pending,
      message: 'Your payment is still being confirmed. We will notify you as soon as it is.',
      payment: state.payment,
    ));
  }

  Future<void> _look(String paymentId, {bool quiet = false}) async {
    try {
      final p = await _repo.get(paymentId);
      if (p.confirmed || p.needsReview) await _settle(p);
    } catch (_) {
      if (!quiet) rethrow;
    }
  }

  /// "Check again" on the pending screen.
  Future<void> checkAgain() async {
    final id = _paymentId ?? state.payment?.id;
    if (id == null || state.busy) return;
    _set(PayState(phase: PayPhase.verifying, payment: state.payment));
    try {
      await _settle(await _repo.get(id));
    } catch (_) {
      _set(PayState(
        phase: PayPhase.pending,
        message: 'Still unable to confirm. Please try again in a moment.',
        payment: state.payment,
      ));
    }
  }
}

final paymentFlowProvider =
    NotifierProvider.autoDispose.family<PaymentFlowController, PayState, String>(PaymentFlowController.new);
