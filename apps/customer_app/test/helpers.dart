import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:flutter_shared/testing.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:zuruv_customer/app.dart';
import 'package:zuruv_customer/core/config/app_config.dart';
import 'package:zuruv_customer/core/storage/preferences.dart';
import 'package:zuruv_customer/features/location/location_service.dart';
import 'package:zuruv_customer/features/profile/avatar_service.dart';
import 'package:zuruv_customer/shared/models/catalog.dart';
import 'package:zuruv_customer/shared/models/venue.dart';
import 'package:zuruv_customer/shared/repositories/profile_repository.dart';
import 'package:zuruv_customer/shared/repositories/venue_repository.dart';

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

/// In-memory stand-in for the API. Records what the app asked for.
class FakeVenueRepository implements VenueRepository {
  FakeVenueRepository({
    List<VenueSummary>? venues,
    this.categoryList = const [badminton, tennis, swimming],
    this.cityList = const [bengaluru, mumbai],
    this.details = const {},
  }) : all = venues ?? [venue('v1', 'Ace Arena', rating: 4.6, reviews: 12), venue('v2', 'Baseline Club', price: 90000)];

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
    var list = all.where((v) {
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
  })  : gateway = gateway ?? FakeAuthGateway(hasSession: true, me: meWith(AppRole.customer)),
        venues = venues ?? FakeVenueRepository(),
        profiles = profiles ?? FakeProfileRepository(),
        location = location ?? FakeLocationService();

  final FakeAuthGateway gateway;
  final FakeVenueRepository venues;
  final FakeProfileRepository profiles;
  final FakeLocationService location;

  Future<Widget> app({Map<String, Object> prefs = const {PrefKeys.onboardingDone: true}}) async {
    SharedPreferences.setMockInitialValues(prefs);
    final sp = await SharedPreferences.getInstance();
    return ProviderScope(
      overrides: [
        sharedPreferencesProvider.overrideWithValue(sp),
        authGatewayProvider.overrideWithValue(gateway),
        expectedRoleProvider.overrideWithValue(AppRole.customer),
        authUiConfigProvider.overrideWithValue(const AuthUiConfig(appName: 'ZURUV', role: AppRole.customer)),
        venueRepositoryProvider.overrideWithValue(venues),
        profileRepositoryProvider.overrideWithValue(profiles),
        locationServiceProvider.overrideWithValue(location),
        avatarServiceProvider.overrideWithValue(FakeAvatarService()),
      ],
      child: const ZuruvCustomerApp(),
    );
  }

  /// Boots the app, runs out the splash and lets everything settle.
  Future<void> pump(WidgetTester tester, {Map<String, Object> prefs = const {PrefKeys.onboardingDone: true}}) async {
    await tester.pumpWidget(await app(prefs: prefs));
    await tester.pump();
    await tester.pump(AppConfig.splashDuration + const Duration(milliseconds: 100));
    await tester.pumpAndSettle();
  }
}

Finder inNavBar(String label) => find.descendant(of: find.byType(NavigationBar), matching: find.text(label));
