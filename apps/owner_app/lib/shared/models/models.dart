// Plain data classes for the Owner API. Parsing is tolerant of missing optional fields and never
// invents values: anything the API leaves out stays null.

DateTime _dt(Object? v) => DateTime.parse(v as String);
double? _d(Object? v) => (v as num?)?.toDouble();

class City {
  const City({required this.id, required this.name, this.state});
  factory City.fromJson(Map<String, dynamic> j) =>
      City(id: j['id'] as String, name: j['name'] as String, state: j['state'] as String?);
  final String id;
  final String name;
  final String? state;
  String get label => state == null || state!.isEmpty ? name : '$name, $state';
}

class Category {
  const Category({required this.id, required this.slug, required this.name, this.iconKey});
  factory Category.fromJson(Map<String, dynamic> j) => Category(
        id: j['id'] as String,
        slug: j['slug'] as String,
        name: j['name'] as String,
        iconKey: j['icon_key'] as String?,
      );
  final String id;
  final String slug;
  final String name;
  final String? iconKey;
}

class Amenity {
  const Amenity({required this.id, required this.slug, required this.name});
  factory Amenity.fromJson(Map<String, dynamic> j) =>
      Amenity(id: j['id'] as String, slug: j['slug'] as String, name: j['name'] as String);
  final String id;
  final String slug;
  final String name;
}

class VenueImage {
  const VenueImage({required this.id, this.url, this.altText, required this.isCover, required this.sortOrder});
  factory VenueImage.fromJson(Map<String, dynamic> j) => VenueImage(
        id: j['id'] as String,
        url: j['url'] as String?,
        altText: j['alt_text'] as String?,
        isCover: j['is_cover'] as bool? ?? false,
        sortOrder: j['sort_order'] as int? ?? 0,
      );
  final String id;
  final String? url;
  final String? altText;
  final bool isCover;
  final int sortOrder;
}

/// A venue as listed on "My Venues".
class OwnerVenueCard {
  const OwnerVenueCard({
    required this.id,
    required this.name,
    required this.status,
    this.cityName,
    this.addressLine,
    this.coverImageUrl,
    this.imageCount = 0,
    this.categories = const [],
    this.startingPricePaise,
    this.currency = 'INR',
    this.ratingAvg,
    this.ratingCount = 0,
  });
  factory OwnerVenueCard.fromJson(Map<String, dynamic> j) => OwnerVenueCard(
        id: j['id'] as String,
        name: j['name'] as String,
        status: j['status'] as String,
        cityName: j['city_name'] as String?,
        addressLine: j['address_line'] as String?,
        coverImageUrl: j['cover_image_url'] as String?,
        imageCount: j['image_count'] as int? ?? 0,
        categories: [for (final c in (j['categories'] as List<dynamic>? ?? [])) c as String],
        startingPricePaise: j['starting_price_paise'] as int?,
        currency: j['currency'] as String? ?? 'INR',
        ratingAvg: _d(j['rating_avg']),
        ratingCount: j['rating_count'] as int? ?? 0,
      );
  final String id;
  final String name;
  final String status; // draft | published | archived
  final String? cityName;
  final String? addressLine;
  final String? coverImageUrl;
  final int imageCount;
  final List<String> categories;
  final int? startingPricePaise;
  final String currency;
  final double? ratingAvg;
  final int ratingCount;

  bool get isPublished => status == 'published';
}

class OwnerVenueDetail {
  const OwnerVenueDetail({
    required this.card,
    this.description,
    this.cityId,
    this.state,
    this.postalCode,
    this.latitude,
    this.longitude,
    this.contactPhone,
    this.timezone = 'Asia/Kolkata',
    this.categoryIds = const [],
    this.amenityIds = const [],
    this.images = const [],
    this.publishBlockers = const [],
  });
  factory OwnerVenueDetail.fromJson(Map<String, dynamic> j) => OwnerVenueDetail(
        card: OwnerVenueCard.fromJson(j),
        description: j['description'] as String?,
        cityId: j['city_id'] as String?,
        state: j['state'] as String?,
        postalCode: j['postal_code'] as String?,
        latitude: _d(j['latitude']),
        longitude: _d(j['longitude']),
        contactPhone: j['contact_phone'] as String?,
        timezone: j['timezone'] as String? ?? 'Asia/Kolkata',
        categoryIds: [for (final c in (j['category_details'] as List<dynamic>? ?? [])) (c as Map<String, dynamic>)['id'] as String],
        amenityIds: [for (final a in (j['amenities'] as List<dynamic>? ?? [])) (a as Map<String, dynamic>)['id'] as String],
        images: [
          for (final i in (j['images'] as List<dynamic>? ?? [])) VenueImage.fromJson(i as Map<String, dynamic>)
        ],
        publishBlockers: [for (final b in (j['publish_blockers'] as List<dynamic>? ?? [])) b as String],
      );
  final OwnerVenueCard card;
  final String? description;
  final String? cityId;
  final String? state;
  final String? postalCode;
  final double? latitude;
  final double? longitude;
  final String? contactPhone;
  final String timezone;
  final List<String> categoryIds;
  final List<String> amenityIds;
  final List<VenueImage> images;
  final List<String> publishBlockers;

  String get id => card.id;
  String get name => card.name;
  bool get canPublish => publishBlockers.isEmpty;
}

class VenuePage {
  const VenuePage({required this.items, required this.hasMore});
  factory VenuePage.fromJson(Map<String, dynamic> j) => VenuePage(
        items: [for (final i in (j['items'] as List<dynamic>)) OwnerVenueCard.fromJson(i as Map<String, dynamic>)],
        hasMore: j['has_more'] as bool? ?? false,
      );
  final List<OwnerVenueCard> items;
  final bool hasMore;
}

/// Fields sent when creating or updating a venue. `toJson` includes only what is set, so a PATCH
/// never overwrites fields the form did not touch. `clear` lists nullable fields to set to null.
class VenueDraft {
  const VenueDraft({
    this.name,
    this.description,
    this.addressLine,
    this.cityId,
    this.postalCode,
    this.latitude,
    this.longitude,
    this.contactPhone,
    this.startingPricePaise,
    this.categoryIds,
    this.amenityIds,
    this.clear = const {},
  });
  final String? name;
  final String? description;
  final String? addressLine;
  final String? cityId;
  final String? postalCode;
  final double? latitude;
  final double? longitude;
  final String? contactPhone;
  final int? startingPricePaise;
  final List<String>? categoryIds;
  final List<String>? amenityIds;
  final Set<String> clear;

  Map<String, dynamic> toJson() => {
        if (name != null) 'name': name,
        if (description != null) 'description': description,
        if (addressLine != null) 'address_line': addressLine,
        if (cityId != null) 'city_id': cityId,
        if (postalCode != null) 'postal_code': postalCode,
        if (latitude != null) 'latitude': latitude,
        if (longitude != null) 'longitude': longitude,
        if (contactPhone != null) 'contact_phone': contactPhone,
        if (startingPricePaise != null) 'starting_price_paise': startingPricePaise,
        if (categoryIds != null) 'category_ids': categoryIds,
        if (amenityIds != null) 'amenity_ids': amenityIds,
        for (final k in clear) k: null,
      };
}

// ------------------------------------------------------------------ schedules
class TimeInterval {
  const TimeInterval(this.opensAt, this.closesAt);
  factory TimeInterval.fromJson(Map<String, dynamic> j) => TimeInterval(j['opens_at'] as String, j['closes_at'] as String);
  final String opensAt; // "HH:MM" or "HH:MM:SS"
  final String closesAt;
  Map<String, dynamic> toJson() => {'opens_at': _full(opensAt), 'closes_at': _full(closesAt)};
  static String _full(String t) => t.length == 5 ? '$t:00' : t;

  @override
  bool operator ==(Object other) =>
      other is TimeInterval && other.opensAt.substring(0, 5) == opensAt.substring(0, 5) && other.closesAt.substring(0, 5) == closesAt.substring(0, 5);
  @override
  int get hashCode => Object.hash(opensAt.substring(0, 5), closesAt.substring(0, 5));
}

class DayHours {
  const DayHours(this.weekday, this.intervals);
  factory DayHours.fromJson(Map<String, dynamic> j) => DayHours(
        j['weekday'] as int,
        [for (final i in (j['intervals'] as List<dynamic>)) TimeInterval.fromJson(i as Map<String, dynamic>)],
      );
  final int weekday; // 0 = Monday
  final List<TimeInterval> intervals; // empty = closed
  bool get isOpen => intervals.isNotEmpty;
  Map<String, dynamic> toJson() => {'weekday': weekday, 'intervals': [for (final i in intervals) i.toJson()]};
}

class SpecialDate {
  const SpecialDate({required this.onDate, required this.isClosed, this.opensAt, this.closesAt, this.note});
  factory SpecialDate.fromJson(Map<String, dynamic> j) => SpecialDate(
        onDate: j['on_date'] as String,
        isClosed: j['is_closed'] as bool,
        opensAt: j['opens_at'] as String?,
        closesAt: j['closes_at'] as String?,
        note: j['note'] as String?,
      );
  final String onDate; // yyyy-MM-dd
  final bool isClosed;
  final String? opensAt;
  final String? closesAt;
  final String? note;
  Map<String, dynamic> toJson() => {
        'on_date': onDate,
        'is_closed': isClosed,
        if (!isClosed) 'opens_at': TimeInterval._full(opensAt!),
        if (!isClosed) 'closes_at': TimeInterval._full(closesAt!),
        if (note != null && note!.isNotEmpty) 'note': note,
      };
}

class VenueSchedule {
  const VenueSchedule({required this.regular, required this.special, this.slotStatus, this.slotMessage, this.courtCount = 0});
  factory VenueSchedule.fromJson(Map<String, dynamic> j) {
    final slot = j['slot_configuration'] as Map<String, dynamic>?;
    return VenueSchedule(
      regular: [for (final d in (j['regular'] as List<dynamic>)) DayHours.fromJson(d as Map<String, dynamic>)],
      special: [for (final s in (j['special'] as List<dynamic>)) SpecialDate.fromJson(s as Map<String, dynamic>)],
      slotStatus: slot?['status'] as String?,
      slotMessage: slot?['message'] as String?,
      courtCount: (slot?['configured_resources'] as num?)?.toInt() ?? 0,
    );
  }
  final List<DayHours> regular; // always 7 entries
  final List<SpecialDate> special;
  final String? slotStatus;
  final String? slotMessage;
  final int courtCount; // courts with a slot length and price
}

// ------------------------------------------------------------------ business data
/// A metric the backend cannot compute yet. Carries what it is waiting for; never a fake number.
class Unavailable {
  const Unavailable({required this.dependsOn, required this.message});
  factory Unavailable.fromJson(Map<String, dynamic> j) =>
      Unavailable(dependsOn: j['depends_on'] as String? ?? '', message: j['message'] as String? ?? '');
  final String dependsOn;
  final String message;
}

class PerformanceVenue {
  const PerformanceVenue({
    required this.venueId,
    required this.name,
    required this.status,
    this.ratingAvg,
    this.ratingCount = 0,
    this.coverImageUrl,
  });
  factory PerformanceVenue.fromJson(Map<String, dynamic> j) => PerformanceVenue(
        venueId: j['venue_id'] as String,
        name: j['name'] as String,
        status: j['status'] as String,
        ratingAvg: _d(j['rating_avg']),
        ratingCount: j['rating_count'] as int? ?? 0,
        coverImageUrl: j['cover_image_url'] as String?,
      );
  final String venueId;
  final String name;
  final String status;
  final double? ratingAvg;
  final int ratingCount;
  final String? coverImageUrl;
}

class OwnerNotification {
  const OwnerNotification({required this.id, required this.type, required this.title, this.body, required this.isRead, required this.createdAt});
  factory OwnerNotification.fromJson(Map<String, dynamic> j) => OwnerNotification(
        id: j['id'] as String,
        type: j['type'] as String,
        title: j['title'] as String,
        body: j['body'] as String?,
        isRead: j['is_read'] as bool? ?? false,
        createdAt: _dt(j['created_at']),
      );
  final String id;
  final String type;
  final String title;
  final String? body;
  final bool isRead;
  final DateTime createdAt;
  OwnerNotification asRead() =>
      OwnerNotification(id: id, type: type, title: title, body: body, isRead: true, createdAt: createdAt);
}

class NotificationPage {
  const NotificationPage({required this.items, required this.unreadCount, required this.hasMore});
  factory NotificationPage.fromJson(Map<String, dynamic> j) => NotificationPage(
        items: [for (final n in (j['items'] as List<dynamic>)) OwnerNotification.fromJson(n as Map<String, dynamic>)],
        unreadCount: j['unread_count'] as int? ?? 0,
        hasMore: j['has_more'] as bool? ?? false,
      );
  final List<OwnerNotification> items;
  final int unreadCount;
  final bool hasMore;
}

class BookingOverview {
  const BookingOverview({required this.upcoming, required this.completed, required this.cancelled});
  factory BookingOverview.fromJson(Map<String, dynamic> j) => BookingOverview(
        upcoming: (j['upcoming'] as num?)?.toInt() ?? 0,
        completed: (j['completed'] as num?)?.toInt() ?? 0,
        cancelled: (j['cancelled'] as num?)?.toInt() ?? 0,
      );
  final int upcoming;
  final int completed;
  final int cancelled;
}

class Dashboard {
  const Dashboard({
    required this.venuesTotal,
    required this.venuesPublished,
    required this.venuesDraft,
    this.averageRating,
    required this.ratingsCount,
    required this.performance,
    required this.recent,
    required this.totalBookings,
    required this.totalRevenue,
    required this.monthlyRevenue,
    required this.bookingOverview,
    required this.averageUtilization,
  });
  factory Dashboard.fromJson(Map<String, dynamic> j) => Dashboard(
        venuesTotal: j['venues_total'] as int,
        venuesPublished: j['venues_published'] as int,
        venuesDraft: j['venues_draft'] as int,
        averageRating: _d(j['average_rating']),
        ratingsCount: j['ratings_count'] as int? ?? 0,
        performance: [for (final v in (j['venue_performance'] as List<dynamic>)) PerformanceVenue.fromJson(v as Map<String, dynamic>)],
        recent: [for (final n in (j['recent_activity'] as List<dynamic>)) OwnerNotification.fromJson(n as Map<String, dynamic>)],
        totalBookings: (j['total_bookings'] as num?)?.toInt() ?? 0,
        totalRevenue: Unavailable.fromJson(j['total_revenue'] as Map<String, dynamic>),
        monthlyRevenue: Unavailable.fromJson(j['monthly_revenue'] as Map<String, dynamic>),
        bookingOverview: BookingOverview.fromJson(j['booking_overview'] as Map<String, dynamic>),
        averageUtilization: Unavailable.fromJson(j['average_utilization'] as Map<String, dynamic>),
      );
  final int venuesTotal;
  final int venuesPublished;
  final int venuesDraft;
  final double? averageRating;
  final int ratingsCount;
  final List<PerformanceVenue> performance;
  final List<OwnerNotification> recent;
  final int totalBookings;
  final Unavailable totalRevenue;
  final Unavailable monthlyRevenue;
  final BookingOverview bookingOverview;
  final Unavailable averageUtilization;
}

class Analytics {
  const Analytics({
    required this.performance,
    required this.totalBookings,
    required this.revenue,
    required this.utilization,
    required this.bookingTrends,
    required this.popularSlots,
  });
  factory Analytics.fromJson(Map<String, dynamic> j) => Analytics(
        performance: [for (final v in (j['venue_performance'] as List<dynamic>)) PerformanceVenue.fromJson(v as Map<String, dynamic>)],
        totalBookings: Unavailable.fromJson(j['total_bookings'] as Map<String, dynamic>),
        revenue: Unavailable.fromJson(j['revenue'] as Map<String, dynamic>),
        utilization: Unavailable.fromJson(j['utilization'] as Map<String, dynamic>),
        bookingTrends: Unavailable.fromJson(j['booking_trends'] as Map<String, dynamic>),
        popularSlots: Unavailable.fromJson(j['popular_time_slots'] as Map<String, dynamic>),
      );
  final List<PerformanceVenue> performance;
  final Unavailable totalBookings;
  final Unavailable revenue;
  final Unavailable utilization;
  final Unavailable bookingTrends;
  final Unavailable popularSlots;
}

/// Response of the endpoints whose data does not exist yet (bookings, earnings, reviews).
/// The list is empty while `available` is false; it is never filled with sample rows.
class PendingFeature {
  const PendingFeature({required this.dependsOn, required this.message});
  factory PendingFeature.fromJson(Map<String, dynamic> j) =>
      PendingFeature(dependsOn: j['depends_on'] as String? ?? '', message: j['message'] as String? ?? '');
  final String dependsOn;
  final String message;
}

/// A confirmed payment for one of the owner's bookings (gross amount, as paid by the customer).
class OwnerPayment {
  const OwnerPayment({
    required this.id,
    required this.bookingId,
    required this.bookingCode,
    required this.venueName,
    required this.courtName,
    required this.amountPaise,
    required this.currency,
    required this.status,
    required this.createdAt,
    this.method,
    this.capturedAt,
  });
  factory OwnerPayment.fromJson(Map<String, dynamic> j) => OwnerPayment(
        id: j['id'] as String,
        bookingId: j['booking_id'] as String,
        bookingCode: j['booking_code'] as String? ?? '',
        venueName: j['venue_name'] as String? ?? '',
        courtName: j['resource_name'] as String? ?? '',
        amountPaise: (j['amount_paise'] as num?)?.toInt() ?? 0,
        currency: j['currency'] as String? ?? 'INR',
        status: j['status'] as String? ?? '',
        method: j['method'] as String?,
        createdAt: DateTime.parse(j['created_at'] as String),
        capturedAt: j['captured_at'] == null ? null : DateTime.parse(j['captured_at'] as String),
      );
  final String id;
  final String bookingId;
  final String bookingCode;
  final String venueName;
  final String courtName;
  final int amountPaise;
  final String currency;
  final String status;
  final String? method;
  final DateTime createdAt;
  final DateTime? capturedAt;
}

class OwnerPaymentPage {
  const OwnerPaymentPage({required this.items, required this.hasMore});
  factory OwnerPaymentPage.fromJson(Map<String, dynamic> j) => OwnerPaymentPage(
        items: [for (final p in (j['items'] as List<dynamic>? ?? const [])) OwnerPayment.fromJson(p as Map<String, dynamic>)],
        hasMore: j['has_more'] as bool? ?? false,
      );
  final List<OwnerPayment> items;
  final bool hasMore;
}

class VenueGross {
  const VenueGross({required this.venueId, required this.venueName, required this.grossPaidPaise, required this.payments});
  factory VenueGross.fromJson(Map<String, dynamic> j) => VenueGross(
        venueId: j['venue_id'] as String,
        venueName: j['venue_name'] as String? ?? '',
        grossPaidPaise: (j['gross_paid_paise'] as num?)?.toInt() ?? 0,
        payments: (j['payments'] as num?)?.toInt() ?? 0,
      );
  final String venueId;
  final String venueName;
  final int grossPaidPaise;
  final int payments;
}

/// Only confirmed facts: what customers actually paid. Deductions, net earnings and payouts depend on
/// rules that are not approved yet, so the API (and this app) reports them as unavailable.
class OwnerEarnings {
  const OwnerEarnings({
    required this.currency,
    required this.grossPaidPaise,
    required this.paymentsCount,
    required this.byVenue,
    required this.deductions,
    required this.netEarnings,
    required this.payouts,
  });
  factory OwnerEarnings.fromJson(Map<String, dynamic> j) => OwnerEarnings(
        currency: j['currency'] as String? ?? 'INR',
        grossPaidPaise: (j['gross_paid_paise'] as num?)?.toInt() ?? 0,
        paymentsCount: (j['payments_count'] as num?)?.toInt() ?? 0,
        byVenue: [for (final v in (j['by_venue'] as List<dynamic>? ?? const [])) VenueGross.fromJson(v as Map<String, dynamic>)],
        deductions: PendingFeature.fromJson((j['deductions'] as Map<String, dynamic>?) ?? const {}),
        netEarnings: PendingFeature.fromJson((j['net_earnings'] as Map<String, dynamic>?) ?? const {}),
        payouts: PendingFeature.fromJson((j['payouts'] as Map<String, dynamic>?) ?? const {}),
      );
  final String currency;
  final int grossPaidPaise;
  final int paymentsCount;
  final List<VenueGross> byVenue;
  final PendingFeature deductions;
  final PendingFeature netEarnings;
  final PendingFeature payouts;
}

class OwnerBusiness {
  const OwnerBusiness({required this.businessName, this.businessPhone, this.businessEmail, this.businessAddress});
  factory OwnerBusiness.fromJson(Map<String, dynamic> j) => OwnerBusiness(
        businessName: j['business_name'] as String? ?? '',
        businessPhone: j['business_phone'] as String?,
        businessEmail: j['business_email'] as String?,
        businessAddress: j['business_address'] as String?,
      );
  final String businessName;
  final String? businessPhone;
  final String? businessEmail;
  final String? businessAddress;
}


// ------------------------------------------------------------------ bookings, courts, blocks (Step 6)
class BookingEvent {
  const BookingEvent({required this.toStatus, required this.actorRole, required this.createdAt, this.reason});
  factory BookingEvent.fromJson(Map<String, dynamic> j) => BookingEvent(
        toStatus: j['to_status'] as String,
        actorRole: j['actor_role'] as String,
        reason: j['reason'] as String?,
        createdAt: DateTime.parse(j['created_at'] as String),
      );
  final String toStatus;
  final String actorRole;
  final String? reason;
  final DateTime createdAt;
}

String bookingStatusLabel(String status) => switch (status) {
      'pending_payment' => 'Awaiting payment',
      'payment_failed' => 'Payment failed',
      'confirmed' => 'Confirmed',
      'expired' => 'Expired',
      'cancelled_by_customer' => 'Cancelled by customer',
      'cancelled_by_owner' => 'Cancelled by venue',
      'completed' => 'Completed',
      'refund_pending' => 'Refund pending',
      'refunded' => 'Refunded',
      _ => status,
    };

/// A booking at one of the owner's venues. Shows the customer's name only: phone and e-mail
/// visibility is an open decision (N9). Owners cannot change a booking's status (N22).
class OwnerBooking {
  const OwnerBooking({
    required this.id,
    required this.code,
    required this.status,
    required this.paymentStatus,
    required this.venueName,
    required this.courtName,
    required this.bookingDate,
    required this.localStart,
    required this.localEnd,
    required this.durationMinutes,
    required this.currency,
    required this.totalAmountPaise,
    required this.customerName,
    this.history = const [],
  });
  factory OwnerBooking.fromJson(Map<String, dynamic> j) => OwnerBooking(
        id: j['id'] as String,
        code: j['booking_code'] as String,
        status: j['status'] as String,
        paymentStatus: j['payment_status'] as String? ?? 'unpaid',
        venueName: j['venue_name'] as String,
        courtName: j['resource_name'] as String,
        bookingDate: j['booking_date'] as String,
        localStart: j['local_start'] as String,
        localEnd: j['local_end'] as String,
        durationMinutes: (j['duration_minutes'] as num?)?.toInt() ?? 0,
        currency: j['currency'] as String? ?? 'INR',
        totalAmountPaise: (j['total_amount_paise'] as num?)?.toInt() ?? 0,
        customerName: j['customer_name'] as String? ?? '',
        history: [for (final e in (j['history'] as List<dynamic>? ?? const [])) BookingEvent.fromJson(e as Map<String, dynamic>)],
      );
  final String id;
  final String code;
  final String status;
  final String paymentStatus;
  final String venueName;
  final String courtName;
  final String bookingDate; // yyyy-MM-dd, venue-local
  final String localStart;
  final String localEnd;
  final int durationMinutes;
  final String currency;
  final int totalAmountPaise;
  final String customerName;
  final List<BookingEvent> history;
  String get statusLabel => bookingStatusLabel(status);
}

class OwnerBookingPage {
  const OwnerBookingPage({required this.items, required this.hasMore});
  factory OwnerBookingPage.fromJson(Map<String, dynamic> j) => OwnerBookingPage(
        items: [for (final b in (j['items'] as List<dynamic>? ?? const [])) OwnerBooking.fromJson(b as Map<String, dynamic>)],
        hasMore: j['has_more'] as bool? ?? false,
      );
  final List<OwnerBooking> items;
  final bool hasMore;
}

/// A bookable court. A court without a slot length and a price is not open for booking.
class Court {
  const Court({
    required this.id,
    required this.name,
    required this.isActive,
    this.slotMinutes,
    this.slotPricePaise,
  });
  factory Court.fromJson(Map<String, dynamic> j) => Court(
        id: j['id'] as String,
        name: j['name'] as String,
        isActive: j['is_active'] as bool? ?? true,
        slotMinutes: (j['slot_minutes'] as num?)?.toInt(),
        slotPricePaise: (j['slot_price_paise'] as num?)?.toInt(),
      );
  final String id;
  final String name;
  final bool isActive;
  final int? slotMinutes;
  final int? slotPricePaise;
  bool get configured => slotMinutes != null && slotPricePaise != null;
}

/// A temporary unavailable period (whole venue when [courtId] is null).
class TimeBlock {
  const TimeBlock({required this.id, required this.startsAt, required this.endsAt, this.courtId, this.reason});
  factory TimeBlock.fromJson(Map<String, dynamic> j) => TimeBlock(
        id: j['id'] as String,
        courtId: j['resource_id'] as String?,
        startsAt: DateTime.parse(j['starts_at'] as String),
        endsAt: DateTime.parse(j['ends_at'] as String),
        reason: j['reason'] as String?,
      );
  final String id;
  final String? courtId;
  final DateTime startsAt;
  final DateTime endsAt;
  final String? reason;
}
