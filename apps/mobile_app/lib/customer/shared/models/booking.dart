/// Booking models. Parsed defensively; the server decides availability, price and status.

int _int(Object? v) => (v as num?)?.toInt() ?? 0;

class Slot {
  const Slot({
    required this.startsAt,
    required this.endsAt,
    required this.localStart,
    required this.localEnd,
    required this.pricePaise,
  });

  final DateTime startsAt; // UTC instant; sent back verbatim when booking
  final DateTime endsAt;
  final String localStart; // "HH:MM" in the venue's time zone
  final String localEnd;
  final int pricePaise;

  factory Slot.fromJson(Map<String, dynamic> j) => Slot(
        startsAt: DateTime.parse(j['starts_at'] as String),
        endsAt: DateTime.parse(j['ends_at'] as String),
        localStart: j['local_start'] as String,
        localEnd: j['local_end'] as String,
        pricePaise: _int(j['price_paise']),
      );

  @override
  bool operator ==(Object other) => other is Slot && other.startsAt == startsAt;

  @override
  int get hashCode => startsAt.hashCode;
}

enum ResourceState { available, fullyBooked, closed, notConfigured }

ResourceState _state(String? s) => switch (s) {
      'available' => ResourceState.available,
      'fully_booked' => ResourceState.fullyBooked,
      'not_configured' => ResourceState.notConfigured,
      _ => ResourceState.closed,
    };

class CourtAvailability {
  const CourtAvailability({
    required this.resourceId,
    required this.name,
    required this.state,
    required this.slots,
    this.slotMinutes,
    this.slotPricePaise,
    this.currency = 'INR',
    this.message,
  });

  final String resourceId;
  final String name;
  final ResourceState state;
  final List<Slot> slots;
  final int? slotMinutes;
  final int? slotPricePaise;
  final String currency;
  final String? message;

  factory CourtAvailability.fromJson(Map<String, dynamic> j) => CourtAvailability(
        resourceId: j['resource_id'] as String,
        name: j['name'] as String,
        state: _state(j['state'] as String?),
        slotMinutes: (j['slot_minutes'] as num?)?.toInt(),
        slotPricePaise: (j['slot_price_paise'] as num?)?.toInt(),
        currency: (j['currency'] as String?) ?? 'INR',
        message: j['message'] as String?,
        slots: ((j['slots'] as List<dynamic>?) ?? const [])
            .map((e) => Slot.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}

class Availability {
  const Availability({
    required this.venueId,
    required this.date,
    required this.timezone,
    required this.courts,
    this.closedReason,
    this.note,
  });

  final String venueId;
  final String date; // yyyy-MM-dd (venue-local)
  final String timezone;
  final String? closedReason; // special_closure | weekly_closed | null
  final String? note;
  final List<CourtAvailability> courts;

  bool get hasAnySlot => courts.any((c) => c.slots.isNotEmpty);

  factory Availability.fromJson(Map<String, dynamic> j) => Availability(
        venueId: j['venue_id'] as String,
        date: j['date'] as String,
        timezone: j['timezone'] as String,
        closedReason: j['closed_reason'] as String?,
        note: j['note'] as String?,
        courts: ((j['resources'] as List<dynamic>?) ?? const [])
            .map((e) => CourtAvailability.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}

class Quote {
  const Quote({
    required this.resourceId,
    required this.startsAt,
    required this.endsAt,
    required this.durationMinutes,
    required this.currency,
    required this.baseAmountPaise,
    required this.feesPaise,
    required this.taxPaise,
    required this.discountPaise,
    required this.totalAmountPaise,
    required this.note,
  });

  final String resourceId;
  final DateTime startsAt;
  final DateTime endsAt;
  final int durationMinutes;
  final String currency;
  final int baseAmountPaise;
  final int feesPaise;
  final int taxPaise;
  final int discountPaise;
  final int totalAmountPaise;
  final String note;

  factory Quote.fromJson(Map<String, dynamic> j) => Quote(
        resourceId: j['resource_id'] as String,
        startsAt: DateTime.parse(j['starts_at'] as String),
        endsAt: DateTime.parse(j['ends_at'] as String),
        durationMinutes: _int(j['duration_minutes']),
        currency: (j['currency'] as String?) ?? 'INR',
        baseAmountPaise: _int(j['base_amount_paise']),
        feesPaise: _int(j['fees_paise']),
        taxPaise: _int(j['tax_paise']),
        discountPaise: _int(j['discount_paise']),
        totalAmountPaise: _int(j['total_amount_paise']),
        note: (j['note'] as String?) ?? '',
      );
}

class StatusEvent {
  const StatusEvent({required this.toStatus, required this.actorRole, required this.createdAt, this.fromStatus, this.reason});

  final String? fromStatus;
  final String toStatus;
  final String actorRole;
  final String? reason;
  final DateTime createdAt;

  factory StatusEvent.fromJson(Map<String, dynamic> j) => StatusEvent(
        fromStatus: j['from_status'] as String?,
        toStatus: j['to_status'] as String,
        actorRole: j['actor_role'] as String,
        reason: j['reason'] as String?,
        createdAt: DateTime.parse(j['created_at'] as String),
      );
}

String statusLabelFor(String status) => switch (status) {
      'pending_payment' => 'Awaiting payment',
      'payment_failed' => 'Payment failed',
      'confirmed' => 'Confirmed',
      'expired' => 'Expired',
      'cancelled_by_customer' => 'Cancelled',
      'cancelled_by_owner' => 'Cancelled by venue',
      'completed' => 'Completed',
      'refund_pending' => 'Refund pending',
      'refunded' => 'Refunded',
      _ => status,
    };

class Booking {
  const Booking({
    required this.id,
    required this.code,
    required this.status,
    required this.paymentStatus,
    required this.venueId,
    required this.venueName,
    required this.resourceName,
    required this.bookingDate,
    required this.startsAt,
    required this.endsAt,
    required this.localStart,
    required this.localEnd,
    required this.durationMinutes,
    required this.currency,
    required this.totalAmountPaise,
    this.expiresAt,
    this.cancelReason,
    this.canCancel = false,
    this.history = const [],
  });

  final String id;
  final String code;
  final String status;
  final String paymentStatus;
  final String venueId;
  final String venueName;
  final String resourceName;
  final String bookingDate;
  final DateTime startsAt;
  final DateTime endsAt;
  final String localStart;
  final String localEnd;
  final int durationMinutes;
  final String currency;
  final int totalAmountPaise;
  final DateTime? expiresAt;
  final String? cancelReason;
  final bool canCancel;
  final List<StatusEvent> history;

  bool get isHold => status == 'pending_payment' || status == 'payment_failed';

  /// Customer-facing label. Statuses come from the server; unknown ones are shown as-is.
  String get statusLabel => statusLabelFor(status);

  factory Booking.fromJson(Map<String, dynamic> j) => Booking(
        id: j['id'] as String,
        code: j['booking_code'] as String,
        status: j['status'] as String,
        paymentStatus: (j['payment_status'] as String?) ?? 'unpaid',
        venueId: j['venue_id'] as String,
        venueName: j['venue_name'] as String,
        resourceName: j['resource_name'] as String,
        bookingDate: j['booking_date'] as String,
        startsAt: DateTime.parse(j['starts_at'] as String),
        endsAt: DateTime.parse(j['ends_at'] as String),
        localStart: j['local_start'] as String,
        localEnd: j['local_end'] as String,
        durationMinutes: _int(j['duration_minutes']),
        currency: (j['currency'] as String?) ?? 'INR',
        totalAmountPaise: _int(j['total_amount_paise']),
        expiresAt: j['expires_at'] == null ? null : DateTime.parse(j['expires_at'] as String),
        cancelReason: j['cancel_reason'] as String?,
        canCancel: (j['can_cancel'] as bool?) ?? false,
        history: ((j['history'] as List<dynamic>?) ?? const [])
            .map((e) => StatusEvent.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}

class BookingPageData {
  const BookingPageData({required this.items, required this.hasMore});

  final List<Booking> items;
  final bool hasMore;

  factory BookingPageData.fromJson(Map<String, dynamic> j) => BookingPageData(
        items: ((j['items'] as List<dynamic>?) ?? const [])
            .map((e) => Booking.fromJson(e as Map<String, dynamic>))
            .toList(),
        hasMore: (j['has_more'] as bool?) ?? false,
      );
}

class CancellationPreview {
  const CancellationPreview({required this.canCancel, required this.code, required this.message});

  final bool canCancel;
  final String code;
  final String message;

  factory CancellationPreview.fromJson(Map<String, dynamic> j) => CancellationPreview(
        canCancel: (j['can_cancel'] as bool?) ?? false,
        code: (j['code'] as String?) ?? '',
        message: (j['message'] as String?) ?? '',
      );
}
