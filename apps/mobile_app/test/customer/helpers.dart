import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:flutter_shared/testing.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:zuruv/app.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:zuruv/customer/features/venue_details/directions_launcher.dart';
import 'package:zuruv/core/config/app_config.dart';
import 'package:zuruv/core/settings/settings_repository.dart';
import 'package:zuruv/core/storage/preferences.dart';
import '../settings_fakes.dart';
import 'package:zuruv/customer/features/location/location_service.dart';
import 'package:zuruv/customer/features/profile/avatar_service.dart';
import 'package:zuruv/customer/features/payments/checkout_launcher.dart';
import 'package:zuruv/customer/features/payments/payment_flow.dart';
import 'package:zuruv/customer/shared/models/app_notification.dart';
import 'package:zuruv/customer/shared/models/booking.dart';
import 'package:zuruv/customer/shared/models/payment.dart';
import 'package:zuruv/customer/shared/models/review.dart';
import 'package:zuruv/customer/shared/models/catalog.dart';
import 'package:zuruv/customer/shared/models/venue.dart';
import 'package:zuruv/customer/shared/repositories/booking_repository.dart';
import 'package:zuruv/customer/shared/repositories/notification_repository.dart';
import 'package:zuruv/customer/shared/repositories/payment_repository.dart';
import 'package:zuruv/customer/shared/repositories/profile_repository.dart';
import 'package:zuruv/customer/shared/repositories/review_repository.dart';
import 'package:zuruv/customer/shared/repositories/venue_repository.dart';

const bengaluru = City(id: 'c-blr', name: 'Bengaluru', state: 'Karnataka');
const mumbai = City(id: 'c-bom', name: 'Mumbai', state: 'Maharashtra');

const badminton = VenueCategory(id: 'k1', slug: 'badminton', name: 'Badminton', iconKey: 'badminton');
const tennis = VenueCategory(id: 'k2', slug: 'tennis', name: 'Tennis', iconKey: 'tennis');
const swimming = VenueCategory(id: 'k3', slug: 'swimming', name: 'Swimming', iconKey: 'swimming');

VenueSummary venue(
  String id,
  String name, {
  String city = 'Bengaluru',
  int? price = 50000,
  double? rating,
  int reviews = 0,
  bool favorite = false,
  List<String> categories = const ['badminton'],
}) =>
    VenueSummary(
      id: id,
      name: name,
      cityName: city,
      addressLine: 'Koramangala',
      categories: categories,
      startingPricePaise: price,
      ratingAvg: rating,
      ratingCount: reviews,
      isFavorite: favorite,
    );

/// Top-level on purpose: inside the fake, `venue` is its own method.
List<VenueSummary> _defaultVenues() =>
    [venue('v1', 'Ace Arena', rating: 4.6, reviews: 12), venue('v2', 'Baseline Club', price: 90000)];

/// In-memory stand-in for the API. Records what the app asked for.
class FakeVenueRepository implements VenueRepository {
  FakeVenueRepository({
    List<VenueSummary>? venues,
    this.categoryList = const [badminton, tennis, swimming],
    this.cityList = const [bengaluru, mumbai],
    this.details = const {},
  }) : all = venues ?? _defaultVenues();

  final List<VenueSummary> all;
  final List<VenueCategory> categoryList;
  final List<City> cityList;
  final Map<String, VenueDetail> details;

  Object? venuesError;
  Object? detailError;
  bool failFavorites = false;
  final List<VenueQuery> queries = [];
  final List<String> added = [];
  final List<String> removed = [];

  @override
  Future<List<City>> cities() async => cityList;

  @override
  Future<List<VenueCategory>> categories() async => categoryList;

  @override
  Future<VenuePageData> venues(VenueQuery query, {required int offset, CancelToken? cancelToken}) async {
    queries.add(query);
    if (venuesError != null) throw venuesError!;
    final list = all.where((v) {
      if (query.favoritesOnly && !(v.isFavorite || added.contains(v.id))) return false;
      if (query.text != null && query.text!.isNotEmpty && !v.name.toLowerCase().contains(query.text!.toLowerCase())) return false;
      if (query.category != null && !v.categories.contains(query.category)) return false;
      return true;
    }).toList();
    final end = (offset + query.pageSize).clamp(0, list.length);
    final page = list.sublist(offset.clamp(0, list.length), end);
    return VenuePageData(items: page, hasMore: end < list.length);
  }

  @override
  Future<VenueDetail> venue(String id, {double? lat, double? lng}) async {
    if (detailError != null) throw detailError!;
    final d = details[id];
    if (d == null) {
      throw const ApiException(statusCode: 404, code: 'VENUE_NOT_FOUND', message: 'Venue not found.');
    }
    return d;
  }

  @override
  Future<void> addFavorite(String venueId) async {
    if (failFavorites) throw const ApiException(statusCode: 500, code: 'X', message: 'boom');
    added.add(venueId);
  }

  @override
  Future<void> removeFavorite(String venueId) async {
    if (failFavorites) throw const ApiException(statusCode: 500, code: 'X', message: 'boom');
    removed.add(venueId);
  }
}

Slot slot(String hhmm, {int price = 50000}) {
  final h = int.parse(hhmm.split(':')[0]);
  final start = DateTime.utc(2030, 1, 7, h);
  return Slot(
    startsAt: start,
    endsAt: start.add(const Duration(hours: 1)),
    localStart: hhmm,
    localEnd: '${(h + 1).toString().padLeft(2, '0')}:00',
    pricePaise: price,
  );
}

Booking bookingOf(
  String id, {
  String status = 'pending_payment',
  String venueName = 'Ace Arena',
  bool canCancel = true,
  String code = 'ZUR-ABCD2345',
  List<StatusEvent> history = const [],
  String paymentStatus = 'unpaid',
}) =>
    Booking(
      id: id,
      code: code,
      status: status,
      paymentStatus: paymentStatus,
      venueId: 'v1',
      venueName: venueName,
      resourceName: 'Court 1',
      bookingDate: '2030-01-07',
      startsAt: DateTime.utc(2030, 1, 7, 9),
      endsAt: DateTime.utc(2030, 1, 7, 10),
      localStart: '09:00',
      localEnd: '10:00',
      durationMinutes: 60,
      currency: 'INR',
      totalAmountPaise: 50000,
      expiresAt: DateTime.utc(2030, 1, 7, 8),
      canCancel: canCancel,
      history: history,
    );

/// In-memory stand-in for the booking API. Availability and rules are whatever the test says;
/// the app must display them, never invent them.
class FakeBookingRepository implements BookingRepository {
  FakeBookingRepository({List<CourtAvailability>? courts, this.closedReason, this.note, List<Booking>? bookings})
      : courts = courts ??
            [
              CourtAvailability(
                resourceId: 'r1',
                name: 'Court 1',
                state: ResourceState.available,
                slotMinutes: 60,
                slotPricePaise: 50000,
                slots: [slot('09:00'), slot('10:00')],
              ),
            ],
        bookings = bookings ?? [];

  List<CourtAvailability> courts;
  String? closedReason;
  String? note;
  final List<Booking> bookings;

  Object? availabilityError;
  Object? listError;
  Object? quoteError;
  Object? createError;
  CancellationPreview preview = const CancellationPreview(canCancel: true, code: 'OK', message: 'Cancelling releases the slot.');
  final List<String> idempotencyKeys = [];
  final List<String> availabilityDates = [];
  final List<String> cancelled = [];

  @override
  Future<Availability> availability(String venueId, String date, {String? resourceId}) async {
    availabilityDates.add(date);
    if (availabilityError != null) throw availabilityError!;
    return Availability(venueId: venueId, date: date, timezone: 'Asia/Kolkata', courts: courts, closedReason: closedReason, note: note);
  }

  @override
  Future<Quote> quote(String resourceId, DateTime startsAt) async {
    if (quoteError != null) throw quoteError!;
    return Quote(
      resourceId: resourceId,
      startsAt: startsAt,
      endsAt: startsAt.add(const Duration(hours: 1)),
      durationMinutes: 60,
      currency: 'INR',
      baseAmountPaise: 50000,
      feesPaise: 0,
      taxPaise: 0,
      discountPaise: 0,
      totalAmountPaise: 50000,
      note: '',
    );
  }

  @override
  Future<Booking> create(String resourceId, DateTime startsAt, {required String idempotencyKey}) async {
    idempotencyKeys.add(idempotencyKey);
    if (createError != null) {
      final e = createError!;
      throw e;
    }
    final b = bookingOf('b-new');
    bookings.insert(0, b);
    return b;
  }

  @override
  Future<BookingPageData> list(String bucket, {required int offset, int limit = 20}) async {
    if (listError != null) throw listError!;
    final wanted = switch (bucket) {
      'upcoming' => ['pending_payment', 'payment_failed', 'confirmed'],
      'past' => ['completed', 'expired'],
      _ => ['cancelled_by_customer', 'cancelled_by_owner', 'refund_pending', 'refunded'],
    };
    return BookingPageData(items: bookings.where((b) => wanted.contains(b.status)).toList(), hasMore: false);
  }

  @override
  Future<Booking> get(String id) async {
    final found = bookings.where((b) => b.id == id);
    if (found.isEmpty) throw const ApiException(statusCode: 404, code: 'BOOKING_NOT_FOUND', message: 'Booking not found.');
    return found.first;
  }

  @override
  Future<CancellationPreview> cancellationPreview(String id) async => preview;

  @override
  Future<Booking> cancel(String id, {String? reason}) async {
    cancelled.add(id);
    final i = bookings.indexWhere((b) => b.id == id);
    bookings[i] = bookingOf(id, status: 'cancelled_by_customer', canCancel: false);
    return bookings[i];
  }
}

PaymentInfo paymentOf({
  String id = 'p1',
  String bookingId = 'b1',
  String status = 'created',
  bool confirmed = false,
  bool needsReview = false,
  String bookingStatus = 'pending_payment',
  String? failureReason,
}) =>
    PaymentInfo(
      id: id,
      bookingId: bookingId,
      bookingCode: 'ZUR-ABCD2345',
      venueName: 'Ace Arena',
      resourceName: 'Court 1',
      amountPaise: 50000,
      currency: 'INR',
      status: status,
      bookingStatus: bookingStatus,
      bookingPaymentStatus: confirmed ? 'paid' : 'pending',
      confirmed: confirmed,
      needsReview: needsReview,
      failureReason: failureReason,
      razorpayOrderId: 'order_1',
      createdAt: DateTime.utc(2030, 1, 1),
    );

PaymentInfo confirmedPayment({String bookingId = 'b1'}) =>
    paymentOf(bookingId: bookingId, status: 'captured', confirmed: true, bookingStatus: 'confirmed');

/// Stand-in for the payment API. Counts calls so tests can prove nothing is paid or created twice.
class FakePaymentRepository implements PaymentRepository {
  Object? createError;
  Object? verifyError;
  Completer<void>? verifyGate; // hold verify open to observe "Verification in progress"
  PaymentInfo verifyResult = confirmedPayment();
  List<PaymentInfo> getResults = [confirmedPayment()]; // popped in order; the last one repeats
  List<PaymentInfo> historyItems = [];
  Object? historyError;

  final List<String> orders = [];
  final List<({String orderId, String paymentId, String signature})> verifies = [];
  int gets = 0;

  @override
  Future<CreateOrderResult> createOrder(String bookingId) async {
    orders.add(bookingId);
    if (createError != null) throw createError!;
    return CreateOrderResult(
      payment: paymentOf(bookingId: bookingId),
      checkout: const CheckoutConfig(
        keyId: 'rzp_test_fake',
        orderId: 'order_1',
        amountPaise: 50000,
        currency: 'INR',
        name: 'ZURUV',
        description: 'Ace Arena · Court 1',
      ),
    );
  }

  @override
  Future<PaymentInfo> verify({required String orderId, required String paymentId, required String signature}) async {
    verifies.add((orderId: orderId, paymentId: paymentId, signature: signature));
    if (verifyGate != null) await verifyGate!.future;
    if (verifyError != null) {
      final e = verifyError!;
      verifyError = null; // fails once; the retry succeeds
      throw e;
    }
    return verifyResult;
  }

  @override
  Future<PaymentInfo> get(String paymentId) async {
    gets++;
    return getResults.length > 1 ? getResults.removeAt(0) : getResults.first;
  }

  @override
  Future<PaymentPageData> history({required int offset, int limit = 20}) async {
    if (historyError != null) throw historyError!;
    return PaymentPageData(items: historyItems, hasMore: false);
  }
}

/// Scripted Razorpay Checkout: each open() consumes the next result.
class FakeDirectionsLauncher implements DirectionsLauncher {
  final List<(double, double)> opened = [];
  bool succeeds = true;

  @override
  Future<bool> open({required double latitude, required double longitude}) async {
    opened.add((latitude, longitude));
    return succeeds;
  }
}

class FakeCheckoutLauncher implements CheckoutLauncher {
  FakeCheckoutLauncher([List<CheckoutResult>? results]) : results = results ?? [okCheckout()];

  final List<CheckoutResult> results;
  final List<CheckoutConfig> opened = [];

  @override
  Future<CheckoutResult> open(CheckoutConfig config) async {
    opened.add(config);
    return results.length > 1 ? results.removeAt(0) : results.first;
  }
}

CheckoutSuccess okCheckout() => const CheckoutSuccess(orderId: 'order_1', paymentId: 'pay_1', signature: 'sig_1');

class FakeReviewRepository implements ReviewRepository {
  FakeReviewRepository({List<Review>? venueReviews}) : venueList = venueReviews ?? [];

  final List<Review> venueList;
  final Map<String, Review> mine = {};
  final List<String> submitted = [];

  @override
  Future<ReviewPageData> venueReviews(String venueId, {int offset = 0, int limit = 20}) async {
    final avg = venueList.isEmpty ? null : venueList.fold<int>(0, (a, r) => a + r.rating) / venueList.length;
    return ReviewPageData(items: venueList, summary: RatingSummary(average: avg, count: venueList.length), hasMore: false);
  }

  @override
  Future<Review?> myReview(String bookingId) async => mine[bookingId];

  @override
  Future<Review> submit(String bookingId, {required int rating, String? comment}) async {
    submitted.add('$bookingId:$rating:${comment ?? ''}');
    final r = Review(
      id: 'rv$rating', rating: rating, comment: (comment == null || comment.trim().isEmpty) ? null : comment.trim(),
      reviewerName: 'Cathy C.', createdAt: DateTime(2030, 1, 1), replyBody: null,
    );
    mine[bookingId] = r;
    return r;
  }
}

class FakeNotificationRepository implements NotificationRepository {
  List<AppNotification> items = [];
  Object? listError;
  final List<String> read = [];
  int readAll = 0;

  @override
  Future<NotificationPageData> list({int limit = 50}) async {
    if (listError != null) throw listError!;
    return NotificationPageData(items: items, unreadCount: items.where((n) => !n.isRead).length);
  }

  @override
  Future<int> unreadCount() async => items.where((n) => !n.isRead).length;

  @override
  Future<void> markRead(String id) async {
    read.add(id);
    items = [
      for (final n in items)
        n.id == id
            ? AppNotification(id: n.id, type: n.type, title: n.title, body: n.body, isRead: true, createdAt: n.createdAt, bookingId: n.bookingId)
            : n,
    ];
  }

  @override
  Future<void> markAllRead() async {
    readAll++;
    items = [
      for (final n in items)
        AppNotification(id: n.id, type: n.type, title: n.title, body: n.body, isRead: true, createdAt: n.createdAt, bookingId: n.bookingId),
    ];
  }
}

class FakeProfileRepository implements ProfileRepository {
  FakeProfileRepository({this.preferredCityId});

  String? preferredCityId;
  Object? updateError;
  final List<Map<String, dynamic>> updates = [];
  final List<String> preferredCities = [];
  UserProfile profile = const UserProfile(id: 'u1', role: AppRole.customer, status: 'active', fullName: 'Asha');

  @override
  Future<CustomerSettings> me() async => CustomerSettings(profile: profile, preferredCityId: preferredCityId);

  @override
  Future<UserProfile> updateProfile(Map<String, dynamic> changes) async {
    if (updateError != null) throw updateError!;
    updates.add(changes);
    profile = UserProfile(
      id: profile.id,
      role: profile.role,
      status: profile.status,
      fullName: (changes['full_name'] as String?) ?? profile.fullName,
      email: profile.email,
      phone: changes.containsKey('phone') ? changes['phone'] as String? : profile.phone,
      avatarPath: (changes['avatar_path'] as String?) ?? profile.avatarPath,
    );
    return profile;
  }

  @override
  Future<void> setPreferredCity(String cityId) async => preferredCities.add(cityId);
}

class FakeLocationService implements LocationService {
  FakeLocationService({this.current = LocationAccess.denied, this.requestResult = LocationAccess.denied, this.point});

  LocationAccess current;
  LocationAccess requestResult;
  GeoPoint? point;
  int requests = 0;
  int settingsOpened = 0;

  @override
  Future<LocationAccess> status() async => current;

  @override
  Future<LocationAccess> request() async {
    requests++;
    current = requestResult;
    return requestResult;
  }

  @override
  Future<GeoPoint?> currentPoint() async => current == LocationAccess.granted ? point : null;

  @override
  Future<void> openSettings() async => settingsOpened++;
}

class FakeAvatarService implements AvatarService {
  @override
  Future<String> upload({required userId, required bytes, required extension}) async => '$userId/avatar-1.$extension';

  @override
  Future<String?> signedUrl(String path) async => null;

  @override
  Future<void> delete(String path) async {}
}

MeResponse meWith(AppRole role, {String name = 'Asha'}) => MeResponse(
      userId: 'u1',
      hasProfile: true,
      profile: UserProfile(id: 'u1', role: role, status: 'active', fullName: name, email: 'asha@example.com'),
    );

class TestEnv {
  TestEnv({
    FakeAuthGateway? gateway,
    FakeVenueRepository? venues,
    FakeProfileRepository? profiles,
    FakeLocationService? location,
    FakeBookingRepository? bookings,
    FakePaymentRepository? payments,
    FakeCheckoutLauncher? checkout,
    FakeNotificationRepository? notifications,
    FakeReviewRepository? reviews,
    FakeDirectionsLauncher? directions,
    FakeSettingsRepository? settings,
  })  : settings = settings ?? FakeSettingsRepository(),
        gateway = gateway ?? FakeAuthGateway(hasSession: true, me: meWith(AppRole.customer)),
        venues = venues ?? FakeVenueRepository(),
        profiles = profiles ?? FakeProfileRepository(),
        location = location ?? FakeLocationService(),
        bookings = bookings ?? FakeBookingRepository(),
        payments = payments ?? FakePaymentRepository(),
        checkout = checkout ?? FakeCheckoutLauncher(),
        notifications = notifications ?? FakeNotificationRepository(),
        reviews = reviews ?? FakeReviewRepository(),
        directions = directions ?? FakeDirectionsLauncher();

  final FakeAuthGateway gateway;
  final FakeVenueRepository venues;
  final FakeProfileRepository profiles;
  final FakeLocationService location;
  final FakeBookingRepository bookings;
  final FakePaymentRepository payments;
  final FakeCheckoutLauncher checkout;
  final FakeNotificationRepository notifications;
  final FakeReviewRepository reviews;
  final FakeDirectionsLauncher directions;
  final FakeSettingsRepository settings;

  Future<Widget> app({Map<String, Object> prefs = const {PrefKeys.onboardingDone: true}}) async {
    SharedPreferences.setMockInitialValues(prefs);
    final sp = await SharedPreferences.getInstance();
    return ProviderScope(
      overrides: [
        sharedPreferencesProvider.overrideWithValue(sp),
        authGatewayProvider.overrideWithValue(gateway),
        venueRepositoryProvider.overrideWithValue(venues),
        bookingRepositoryProvider.overrideWithValue(bookings),
        paymentRepositoryProvider.overrideWithValue(payments),
        checkoutLauncherProvider.overrideWithValue(checkout),
        notificationRepositoryProvider.overrideWithValue(notifications),
        reviewRepositoryProvider.overrideWithValue(reviews),
        directionsLauncherProvider.overrideWithValue(directions),
        pollConfigProvider.overrideWithValue(const PollConfig(interval: Duration.zero, attempts: 3)),
        profileRepositoryProvider.overrideWithValue(profiles),
        locationServiceProvider.overrideWithValue(location),
        avatarServiceProvider.overrideWithValue(FakeAvatarService()),
        settingsRepositoryProvider.overrideWithValue(settings..profile = gateway.me?.profile),
      ],
      child: const ZuruvApp(),
    );
  }

  /// Boots the app, runs out the splash and lets everything settle.
  Future<void> pump(WidgetTester tester, {Map<String, Object> prefs = const {PrefKeys.onboardingDone: true}}) async {
    // A tall phone-like surface so a whole screen is on-screen (the default test surface is 800x600).
    tester.view.physicalSize = const Size(900, 1800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(await app(prefs: prefs));
    await tester.pump();
    await tester.pump(AppConfig.splashDuration + const Duration(milliseconds: 100));
    await tester.pumpAndSettle();
  }
}

Finder inNavBar(String label) => find.descendant(of: find.byType(NavigationBar), matching: find.text(label));
