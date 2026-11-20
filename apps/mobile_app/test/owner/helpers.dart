import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:flutter_shared/testing.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:zuruv/app.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:zuruv/core/config/app_config.dart';
import 'package:zuruv/core/settings/settings_repository.dart';
import 'package:zuruv/core/storage/preferences.dart';
import '../settings_fakes.dart';
import 'package:zuruv/owner/features/profile/avatar_service.dart';
import 'package:zuruv/owner/features/venue_form/venue_form_screen.dart';
import 'package:zuruv/owner/shared/models/models.dart';
import 'package:zuruv/owner/shared/repositories/owner_repository.dart';

const bengaluru = City(id: 'c1', name: 'Bengaluru', state: 'Karnataka');
const badminton = Category(id: 'k1', slug: 'badminton', name: 'Badminton');
const tennis = Category(id: 'k2', slug: 'tennis', name: 'Tennis');
const parking = Amenity(id: 'a1', slug: 'parking', name: 'Parking');

OwnerVenueCard card(String id, String name, {String status = 'published', double? rating, int count = 0, int? price = 50000}) =>
    OwnerVenueCard(
      id: id,
      name: name,
      status: status,
      cityName: 'Bengaluru',
      addressLine: 'Koramangala',
      categories: const ['Badminton'],
      startingPricePaise: price,
      ratingAvg: rating,
      ratingCount: count,
    );

OwnerVenueDetail detail(OwnerVenueCard c, {List<VenueImage> images = const [], List<String> blockers = const []}) => OwnerVenueDetail(
      card: c,
      cityId: 'c1',
      categoryIds: const ['k1'],
      images: images,
      publishBlockers: blockers,
    );

const unavailable = Unavailable(dependsOn: 'Step 7 (payments)', message: 'Revenue will appear once Step 7 is built.');

Dashboard dashboardWith(List<OwnerVenueCard> venues, {double? rating}) => Dashboard(
      venuesTotal: venues.length,
      venuesPublished: venues.where((v) => v.isPublished).length,
      venuesDraft: venues.where((v) => v.status == 'draft').length,
      averageRating: rating,
      ratingsCount: rating == null ? 0 : 10,
      performance: [for (final v in venues) PerformanceVenue(venueId: v.id, name: v.name, status: v.status, ratingAvg: v.ratingAvg, ratingCount: v.ratingCount)],
      recent: const [],
      totalBookings: 3,
      totalRevenue: unavailable,
      monthlyRevenue: unavailable,
      bookingOverview: const BookingOverview(upcoming: 2, completed: 1, cancelled: 0),
      averageUtilization: unavailable,
    );

/// In-memory stand-in for the Owner API.
class FakeOwnerRepository implements OwnerRepository {
  FakeOwnerRepository({List<OwnerVenueCard>? venues}) : cards = venues ?? [card('v1', 'Ace Arena', rating: 4.6, count: 12), card('v2', 'Draft Court', status: 'draft')];

  final List<OwnerVenueCard> cards;
  final Map<String, List<VenueImage>> images = {};
  Object? venuesError;
  final List<VenueDraft> created = [];
  final Map<String, VenueDraft> updated = {};
  final List<String> deleted = [];
  final List<String> published = [];
  final List<String> unpublished = [];
  final List<String> uploads = [];
  final List<String> removedImages = [];
  final List<String> coverSet = [];
  final List<List<String>> reorders = [];
  List<DayHours>? savedRegular;
  List<SpecialDate>? savedSpecial;
  List<String> publishBlockers = const [];
  final List<String?> venueQueries = [];
  final List<String?> statusFilters = [];
  OwnerBusiness businessData = const OwnerBusiness(businessName: 'Ace Sports', businessPhone: '+919876543210');
  final List<Map<String, dynamic>> businessUpdates = [];

  OwnerVenueDetail _detail(String id) {
    final c = cards.firstWhere((v) => v.id == id);
    return detail(c, images: images[id] ?? const [], blockers: publishBlockers);
  }

  @override
  Future<List<City>> cities() async => const [bengaluru];
  @override
  Future<List<Category>> categories() async => const [badminton, tennis];
  @override
  Future<List<Amenity>> amenities() async => const [parking];

  @override
  Future<OwnerBusiness> business() async => businessData;
  @override
  Future<OwnerBusiness> updateBusiness(Map<String, dynamic> changes) async {
    businessUpdates.add(changes);
    return businessData;
  }

  @override
  Future<UserProfile> updateProfile(Map<String, dynamic> changes) async =>
      UserProfile(id: 'u1', role: AppRole.owner, status: 'active', fullName: (changes['full_name'] as String?) ?? 'Asha');

  @override
  Future<VenuePage> venues({String? query, String? status, int limit = 20, int offset = 0}) async {
    venueQueries.add(query);
    statusFilters.add(status);
    if (venuesError != null) throw venuesError!;
    final list = cards.where((v) {
      if (query != null && query.isNotEmpty && !v.name.toLowerCase().contains(query.toLowerCase())) return false;
      if (status != null && v.status != status) return false;
      return true;
    }).toList();
    return VenuePage(items: list, hasMore: false);
  }

  @override
  Future<OwnerVenueDetail> venue(String id) async {
    if (!cards.any((v) => v.id == id)) {
      throw const ApiException(statusCode: 404, code: 'VENUE_NOT_FOUND', message: 'Venue not found.');
    }
    return _detail(id);
  }

  @override
  Future<OwnerVenueDetail> createVenue(VenueDraft draft) async {
    created.add(draft);
    final c = card('new-${created.length}', draft.name!, status: 'draft');
    cards.add(c);
    return _detail(c.id);
  }

  @override
  Future<OwnerVenueDetail> updateVenue(String id, VenueDraft draft) async {
    updated[id] = draft;
    return _detail(id);
  }

  @override
  Future<OwnerVenueDetail> publish(String id) async {
    if (publishBlockers.isNotEmpty) {
      throw ApiException(statusCode: 422, code: 'PUBLISH_REQUIREMENTS', message: 'This venue is not ready to publish.', details: publishBlockers);
    }
    published.add(id);
    final i = cards.indexWhere((v) => v.id == id);
    cards[i] = card(id, cards[i].name, status: 'published');
    return _detail(id);
  }

  @override
  Future<OwnerVenueDetail> unpublish(String id) async {
    unpublished.add(id);
    final i = cards.indexWhere((v) => v.id == id);
    cards[i] = card(id, cards[i].name, status: 'draft');
    return _detail(id);
  }

  @override
  Future<void> deleteVenue(String id) async {
    deleted.add(id);
    cards.removeWhere((v) => v.id == id);
  }

  @override
  Future<VenueImage> uploadImage(String venueId, {required List<int> bytes, required String filename}) async {
    uploads.add(filename);
    final list = images.putIfAbsent(venueId, () => []);
    final img = VenueImage(id: 'img-${uploads.length}', isCover: list.isEmpty, sortOrder: list.length);
    list.add(img);
    return img;
  }

  @override
  Future<void> deleteImage(String venueId, String imageId) async {
    removedImages.add(imageId);
    images[venueId]?.removeWhere((i) => i.id == imageId);
  }

  @override
  Future<VenueImage> setCover(String venueId, String imageId) async {
    coverSet.add(imageId);
    return images[venueId]!.firstWhere((i) => i.id == imageId);
  }

  @override
  Future<List<VenueImage>> reorderImages(String venueId, List<String> orderedIds) async {
    reorders.add(orderedIds);
    return images[venueId] ?? const [];
  }

  List<DayHours> regular = [for (var d = 0; d < 7; d++) DayHours(d, const [])];
  List<SpecialDate> special = [];

  @override
  Future<VenueSchedule> schedule(String venueId) async =>
      VenueSchedule(regular: regular, special: special, slotStatus: 'not_configured', slotMessage: 'Add a court with a slot length and price to start taking bookings.');

  Object? saveScheduleError;

  @override
  Future<VenueSchedule> saveSchedule(String venueId, {List<DayHours>? regular, List<SpecialDate>? special}) async {
    if (saveScheduleError != null) throw saveScheduleError!;
    if (regular != null) {
      savedRegular = regular;
      this.regular = regular;
    }
    if (special != null) {
      savedSpecial = special;
      this.special = special;
    }
    return schedule(venueId);
  }

  Dashboard? dashboardData;

  @override
  Future<Dashboard> dashboard() async => dashboardData ?? dashboardWith(cards, rating: 4.6);

  @override
  Future<Analytics> analytics({required String from, required String to}) async => const Analytics(
        performance: [],
        totalBookings: unavailable,
        revenue: unavailable,
        utilization: unavailable,
        bookingTrends: unavailable,
        popularSlots: unavailable,
      );

  List<OwnerBooking> bookingList = [];
  Object? bookingsError;
  final Map<String, List<Court>> courtList = {};
  final Map<String, List<TimeBlock>> blockList = {};
  Object? saveCourtError;
  Object? addBlockError;
  final List<Map<String, dynamic>> savedCourts = [];
  final List<String> deletedBlocks = [];
  int _seq = 0;

  @override
  Future<OwnerBookingPage> bookings(String bucket, {int offset = 0, int limit = 20}) async {
    if (bookingsError != null) throw bookingsError!;
    final wanted = switch (bucket) {
      'upcoming' => ['confirmed'],
      'past' => ['completed', 'expired'],
      _ => ['cancelled_by_customer', 'cancelled_by_owner', 'refund_pending', 'refunded'],
    };
    return OwnerBookingPage(items: bookingList.where((b) => wanted.contains(b.status)).toList(), hasMore: false);
  }

  @override
  Future<OwnerBooking> booking(String id) async {
    final found = bookingList.where((b) => b.id == id);
    if (found.isEmpty) throw const ApiException(statusCode: 404, code: 'BOOKING_NOT_FOUND', message: 'Booking not found.');
    return found.first;
  }

  @override
  Future<List<Court>> courts(String venueId) async => courtList[venueId] ?? const [];

  @override
  Future<Court> saveCourt(String venueId, {String? courtId, required Map<String, dynamic> fields}) async {
    if (saveCourtError != null) throw saveCourtError!;
    savedCourts.add({'court_id': courtId, ...fields});
    final list = [...(courtList[venueId] ?? const <Court>[])];
    final i = list.indexWhere((c) => c.id == courtId);
    final old = i >= 0 ? list[i] : null;
    final court = Court(
      id: courtId ?? 'c${++_seq}',
      name: (fields['name'] as String?) ?? old?.name ?? 'Court',
      isActive: (fields['is_active'] as bool?) ?? old?.isActive ?? true,
      slotMinutes: (fields['slot_minutes'] as int?) ?? old?.slotMinutes,
      slotPricePaise: (fields['slot_price_paise'] as int?) ?? old?.slotPricePaise,
    );
    if (i >= 0) {
      list[i] = court;
    } else {
      list.add(court);
    }
    courtList[venueId] = list;
    return court;
  }

  @override
  Future<void> deleteCourt(String venueId, String courtId) async {
    courtList[venueId] = [...(courtList[venueId] ?? const <Court>[])]..removeWhere((c) => c.id == courtId);
  }

  @override
  Future<List<TimeBlock>> blocks(String venueId) async => blockList[venueId] ?? const [];

  @override
  Future<TimeBlock> addBlock(String venueId, {String? courtId, required DateTime startsAt, required DateTime endsAt, String? reason}) async {
    if (addBlockError != null) throw addBlockError!;
    final b = TimeBlock(id: 'blk${++_seq}', courtId: courtId, startsAt: startsAt, endsAt: endsAt, reason: reason);
    blockList[venueId] = [...(blockList[venueId] ?? const <TimeBlock>[]), b];
    return b;
  }

  @override
  Future<void> deleteBlock(String venueId, String blockId) async {
    deletedBlocks.add(blockId);
    blockList[venueId] = [...(blockList[venueId] ?? const <TimeBlock>[])]..removeWhere((b) => b.id == blockId);
  }

  OwnerEarnings earningsResult = const OwnerEarnings(
    currency: 'INR',
    grossPaidPaise: 0,
    paymentsCount: 0,
    byVenue: [],
    deductions: PendingFeature(dependsOn: 'Business rules not approved', message: 'Fees will appear once rules are approved.'),
    netEarnings: PendingFeature(dependsOn: 'Business rules not approved', message: 'Net earnings will appear once rules are approved.'),
    payouts: PendingFeature(dependsOn: 'Business rules not approved', message: 'Payout status will appear once rules are approved.'),
  );
  List<OwnerPayment> paymentList = [];
  Object? earningsError;

  @override
  Future<OwnerEarnings> earnings() async {
    if (earningsError != null) throw earningsError!;
    return earningsResult;
  }

  @override
  Future<OwnerPaymentPage> payments({int offset = 0}) async => OwnerPaymentPage(items: paymentList, hasMore: false);
  List<OwnerReview> reviewList = [];
  final List<String> replies = [];

  @override
  Future<OwnerReviewPage> reviews({int? rating, int offset = 0}) async {
    final shown = reviewList.where((r) => rating == null || r.rating == rating).toList();
    final dist = {for (var i = 1; i <= 5; i++) i: reviewList.where((r) => r.rating == i).length};
    final avg = reviewList.isEmpty ? null : reviewList.fold<int>(0, (a, r) => a + r.rating) / reviewList.length;
    return OwnerReviewPage(
      items: shown,
      summary: RatingSummary(average: avg, count: reviewList.length, distribution: dist),
      hasMore: false,
    );
  }

  @override
  Future<OwnerReview> replyToReview(String reviewId, String body) async {
    replies.add('$reviewId:$body');
    final i = reviewList.indexWhere((r) => r.id == reviewId);
    final r = reviewList[i];
    final updated = OwnerReview(
      id: r.id, rating: r.rating, comment: r.comment, reviewerName: r.reviewerName, venueName: r.venueName,
      bookingCode: r.bookingCode, createdAt: r.createdAt, replyBody: body, replyAt: DateTime(2030, 1, 2),
    );
    reviewList[i] = updated;
    return updated;
  }

  final List<OwnerNotification> notes = [
    OwnerNotification(id: 'n1', type: 'booking.created', title: 'New booking', isRead: false, createdAt: DateTime(2030, 1, 1)),
    OwnerNotification(id: 'n2', type: 'review.created', title: 'New review', isRead: true, createdAt: DateTime(2030, 1, 1)),
  ];
  final List<String> markedRead = [];
  bool markedAll = false;

  @override
  Future<NotificationPage> notifications({String group = 'all', bool unreadOnly = false, int offset = 0}) async {
    final list = notes.where((n) {
      if (unreadOnly && n.isRead) return false;
      if (group == 'bookings') return n.type.startsWith('booking.');
      if (group == 'reviews') return n.type.startsWith('review.');
      if (group == 'payments') return n.type.startsWith('payment.') || n.type.startsWith('payout.');
      return true;
    }).toList();
    return NotificationPage(items: list, unreadCount: notes.where((n) => !n.isRead).length, hasMore: false);
  }

  @override
  Future<void> markRead(String id) async {
    markedRead.add(id);
    final i = notes.indexWhere((n) => n.id == id);
    notes[i] = notes[i].asRead();
  }

  NotificationChannels channels = const NotificationChannels(push: true, email: true);
  final List<Map<String, bool?>> channelUpdates = [];

  PlacesFail? placesFail;
  @override
  Future<List<PlaceSuggestion>> searchPlaces(String q, {String? sessionToken}) async {
    if (placesFail != null) throw placesFail!.error;
    return const [PlaceSuggestion(placeId: 'p1', description: 'Ace Arena Road, Pune')];
  }

  @override
  Future<PlaceDetails> placeDetails(String placeId) async => const PlaceDetails(
        formattedAddress: 'Ace Arena Road, Pune 411001',
        latitude: 18.52,
        longitude: 73.85,
        postalCode: '411001',
      );

  @override
  Future<NotificationChannels> notificationChannels() async => channels;

  @override
  Future<NotificationChannels> setNotificationChannels({bool? push, bool? email}) async {
    channelUpdates.add({'push': push, 'email': email});
    channels = NotificationChannels(push: push ?? channels.push, email: email ?? channels.email);
    return channels;
  }

  @override
  Future<void> markAllRead() async {
    markedAll = true;
    for (var i = 0; i < notes.length; i++) {
      notes[i] = notes[i].asRead();
    }
  }
}

class FakeAvatarService implements AvatarService {
  @override
  Future<String> upload({required userId, required bytes, required extension}) async => '$userId/avatar-1.$extension';
  @override
  Future<String?> signedUrl(String path) async => null;
  @override
  Future<void> delete(String path) async {}
}

class FakePhotoPicker implements PhotoPicker {
  FakePhotoPicker(this.photo);
  PickedPhoto? photo;
  @override
  Future<PickedPhoto?> pick() async => photo;
}

MeResponse meWith(AppRole role, {String name = 'Asha'}) => MeResponse(
      userId: 'u1',
      hasProfile: true,
      profile: UserProfile(id: 'u1', role: role, status: 'active', fullName: name, email: 'asha@example.com'),
    );

class TestEnv {
  TestEnv({FakeAuthGateway? gateway, FakeOwnerRepository? repo, FakePhotoPicker? picker, FakeSettingsRepository? settings})
      : settings = settings ?? FakeSettingsRepository(),
        gateway = gateway ?? FakeAuthGateway(hasSession: true, me: meWith(AppRole.owner)),
        repo = repo ?? FakeOwnerRepository(),
        picker = picker ?? FakePhotoPicker(null);

  final FakeAuthGateway gateway;
  final FakeOwnerRepository repo;
  final FakePhotoPicker picker;
  final FakeSettingsRepository settings;

  Future<Widget> app({Map<String, Object> prefs = const {PrefKeys.onboardingDone: true, PrefKeys.ownerOnboardingDone: true}}) async {
    SharedPreferences.setMockInitialValues(prefs);
    final sp = await SharedPreferences.getInstance();
    return ProviderScope(
      overrides: [
        sharedPreferencesProvider.overrideWithValue(sp),
        authGatewayProvider.overrideWithValue(gateway),
        ownerRepositoryProvider.overrideWithValue(repo),
        avatarServiceProvider.overrideWithValue(FakeAvatarService()),
        photoPickerProvider.overrideWithValue(picker),
        settingsRepositoryProvider.overrideWithValue(settings..profile = gateway.me?.profile),
      ],
      child: const ZuruvApp(),
    );
  }

  Future<void> pump(WidgetTester tester, {Map<String, Object> prefs = const {PrefKeys.onboardingDone: true, PrefKeys.ownerOnboardingDone: true}}) async {
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

/// Scrolls the first scrollable until [finder] is built and visible (long forms build lazily).
Future<void> reveal(WidgetTester tester, Finder finder, {double delta = 300}) =>
    tester.scrollUntilVisible(finder, delta, scrollable: find.byType(Scrollable).first);

OwnerBooking bookingOf(
  String id, {
  String status = 'confirmed',
  String customer = 'Cathy Customer',
  String code = 'ZUR-ABCD2345',
}) =>
    OwnerBooking(
      id: id,
      code: code,
      status: status,
      paymentStatus: 'unpaid',
      venueName: 'Ace Arena',
      courtName: 'Court 1',
      bookingDate: '2030-01-07',
      localStart: '09:00',
      localEnd: '10:00',
      durationMinutes: 60,
      currency: 'INR',
      totalAmountPaise: 50000,
      customerName: customer,
      history: [BookingEvent(toStatus: status, actorRole: 'customer', createdAt: DateTime(2030, 1, 1))],
    );

class PlacesFail {
  const PlacesFail(this.error);
  final Object error;
}
