import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:razorpay_flutter/razorpay_flutter.dart';

import 'package:zuruv/customer/shared/models/payment.dart';

/// What Razorpay Checkout reported. A [CheckoutSuccess] is only a CLAIM from the device: it is sent
/// to the backend for verification and never treated as a confirmed payment by itself.
sealed class CheckoutResult {
  const CheckoutResult();
}

class CheckoutSuccess extends CheckoutResult {
  const CheckoutSuccess({required this.orderId, required this.paymentId, required this.signature});

  final String orderId;
  final String paymentId;
  final String signature;
}

class CheckoutFailure extends CheckoutResult {
  const CheckoutFailure(this.message);

  final String message;
}

class CheckoutCancelled extends CheckoutResult {
  const CheckoutCancelled();
}

/// The connection dropped inside Checkout: the payment may or may not have gone through.
class CheckoutNetworkError extends CheckoutResult {
  const CheckoutNetworkError();
}

abstract class CheckoutLauncher {
  Future<CheckoutResult> open(CheckoutConfig config);
}

/// Real Razorpay Checkout. Only the PUBLIC key id is used here; the order id comes from the backend.
class RazorpayCheckoutLauncher implements CheckoutLauncher {
  @override
  Future<CheckoutResult> open(CheckoutConfig c) {
    final completer = Completer<CheckoutResult>();
    final razorpay = Razorpay();

    void finish(CheckoutResult r) {
      if (!completer.isCompleted) completer.complete(r);
    }

    razorpay.on(Razorpay.EVENT_PAYMENT_SUCCESS, (PaymentSuccessResponse r) {
      final orderId = r.orderId;
      final paymentId = r.paymentId;
      final signature = r.signature;
      if (orderId == null || paymentId == null || signature == null) {
        finish(const CheckoutFailure('Payment could not be confirmed. If money was deducted it will be reconciled.'));
      } else {
        finish(CheckoutSuccess(orderId: orderId, paymentId: paymentId, signature: signature));
      }
    });
    razorpay.on(Razorpay.EVENT_PAYMENT_ERROR, (PaymentFailureResponse r) {
      if (r.code == Razorpay.PAYMENT_CANCELLED) {
        finish(const CheckoutCancelled());
      } else if (r.code == Razorpay.NETWORK_ERROR) {
        finish(const CheckoutNetworkError());
      } else {
        finish(CheckoutFailure(r.message ?? 'The payment did not go through.'));
      }
    });
    razorpay.on(Razorpay.EVENT_EXTERNAL_WALLET, (ExternalWalletResponse r) {
      // The wallet app takes over; the final result is confirmed by the backend/webhook.
      finish(const CheckoutNetworkError());
    });

    razorpay.open({
      'key': c.keyId,
      'order_id': c.orderId,
      'name': c.name,
      'description': c.description,
      'prefill': {
        if (c.prefillName != null) 'name': c.prefillName,
        if (c.prefillEmail != null) 'email': c.prefillEmail,
        if (c.prefillContact != null) 'contact': c.prefillContact,
      },
      'timeout': 600,
    });
    return completer.future.whenComplete(razorpay.clear);
  }
}

final checkoutLauncherProvider = Provider<CheckoutLauncher>((ref) => RazorpayCheckoutLauncher());
