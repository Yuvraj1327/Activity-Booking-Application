// Payment models. The backend decides amounts and statuses; the app only displays them.

int _int(Object? v) => (v as num?)?.toInt() ?? 0;

class PaymentInfo {
  const PaymentInfo({
    required this.id,
    required this.bookingId,
    required this.bookingCode,
    required this.venueName,
    required this.resourceName,
    required this.amountPaise,
    required this.currency,
    required this.status,
    required this.bookingStatus,
    required this.bookingPaymentStatus,
    required this.confirmed,
    required this.needsReview,
    required this.createdAt,
    this.method,
    this.razorpayOrderId,
    this.razorpayPaymentId,
    this.failureReason,
    this.holdExpiresAt,
    this.capturedAt,
  });

  final String id;
  final String bookingId;
  final String bookingCode;
  final String venueName;
  final String resourceName;
  final int amountPaise;
  final String currency;

  /// created | pending | authorized | captured | failed | refunded | partially_refunded
  final String status;
  final String? method;
  final String? razorpayOrderId;
  final String? razorpayPaymentId;
  final String? failureReason;
  final String bookingStatus;
  final String bookingPaymentStatus;

  /// True ONLY when the backend verified the payment AND the booking is confirmed. The app never
  /// shows "booking confirmed" on any other basis.
  final bool confirmed;

  /// Money was taken but the booking could not be confirmed; staff will review.
  final bool needsReview;
  final DateTime? holdExpiresAt;
  final DateTime createdAt;
  final DateTime? capturedAt;

  bool get isFailed => status == 'failed';

  factory PaymentInfo.fromJson(Map<String, dynamic> j) => PaymentInfo(
        id: j['id'] as String,
        bookingId: j['booking_id'] as String,
        bookingCode: (j['booking_code'] as String?) ?? '',
        venueName: (j['venue_name'] as String?) ?? '',
        resourceName: (j['resource_name'] as String?) ?? '',
        amountPaise: _int(j['amount_paise']),
        currency: (j['currency'] as String?) ?? 'INR',
        status: (j['status'] as String?) ?? 'created',
        method: j['method'] as String?,
        razorpayOrderId: j['razorpay_order_id'] as String?,
        razorpayPaymentId: j['razorpay_payment_id'] as String?,
        failureReason: j['failure_reason'] as String?,
        bookingStatus: (j['booking_status'] as String?) ?? '',
        bookingPaymentStatus: (j['booking_payment_status'] as String?) ?? 'unpaid',
        confirmed: (j['confirmed'] as bool?) ?? false,
        needsReview: (j['needs_review'] as bool?) ?? false,
        holdExpiresAt: j['hold_expires_at'] == null ? null : DateTime.parse(j['hold_expires_at'] as String),
        createdAt: DateTime.parse(j['created_at'] as String),
        capturedAt: j['captured_at'] == null ? null : DateTime.parse(j['captured_at'] as String),
      );
}

/// Everything Razorpay Checkout needs. The key id is public; the secret never leaves the server.
class CheckoutConfig {
  const CheckoutConfig({
    required this.keyId,
    required this.orderId,
    required this.amountPaise,
    required this.currency,
    required this.name,
    required this.description,
    this.prefillName,
    this.prefillEmail,
    this.prefillContact,
  });

  final String keyId;
  final String orderId;
  final int amountPaise;
  final String currency;
  final String name;
  final String description;
  final String? prefillName;
  final String? prefillEmail;
  final String? prefillContact;

  factory CheckoutConfig.fromJson(Map<String, dynamic> j) {
    final p = (j['prefill'] as Map<String, dynamic>?) ?? const {};
    return CheckoutConfig(
      keyId: j['key_id'] as String,
      orderId: j['order_id'] as String,
      amountPaise: _int(j['amount_paise']),
      currency: (j['currency'] as String?) ?? 'INR',
      name: (j['name'] as String?) ?? 'ZURUV',
      description: (j['description'] as String?) ?? '',
      prefillName: p['name'] as String?,
      prefillEmail: p['email'] as String?,
      prefillContact: p['contact'] as String?,
    );
  }
}

class CreateOrderResult {
  const CreateOrderResult({required this.payment, required this.checkout});

  final PaymentInfo payment;
  final CheckoutConfig checkout;

  factory CreateOrderResult.fromJson(Map<String, dynamic> j) => CreateOrderResult(
        payment: PaymentInfo.fromJson(j['payment'] as Map<String, dynamic>),
        checkout: CheckoutConfig.fromJson(j['checkout'] as Map<String, dynamic>),
      );
}

class PaymentPageData {
  const PaymentPageData({required this.items, required this.hasMore});

  final List<PaymentInfo> items;
  final bool hasMore;

  factory PaymentPageData.fromJson(Map<String, dynamic> j) => PaymentPageData(
        items: ((j['items'] as List<dynamic>?) ?? const [])
            .map((e) => PaymentInfo.fromJson(e as Map<String, dynamic>))
            .toList(),
        hasMore: (j['has_more'] as bool?) ?? false,
      );
}

String paymentStatusLabel(String status) => switch (status) {
      'created' => 'Not paid',
      'pending' => 'Pending',
      'authorized' => 'Processing',
      'captured' => 'Paid',
      'failed' => 'Failed',
      'refunded' => 'Refunded',
      'partially_refunded' => 'Partially refunded',
      _ => status,
    };
