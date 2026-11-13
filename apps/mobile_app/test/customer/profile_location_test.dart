import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:zuruv/core/storage/preferences.dart';
import 'package:zuruv/customer/features/location/location_controller.dart';
import 'package:zuruv/customer/features/location/location_service.dart';
import 'package:zuruv/customer/shared/repositories/profile_repository.dart';
import 'package:zuruv/customer/shared/repositories/venue_repository.dart';

import 'helpers.dart';

void main() {
  group('Profile', () {
    Future<TestEnv> openEdit(WidgetTester tester, {FakeProfileRepository? profiles}) async {
      final env = TestEnv(profiles: profiles);
      await env.pump(tester);
      await tester.tap(inNavBar('Profile'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Edit profile'));
      await tester.pumpAndSettle();
      return env;
    }

    testWidgets('editing the name saves only the changed field and updates the profile tab', (tester) async {
      final env = await openEdit(tester);
      await tester.enterText(find.widgetWithText(TextFormField, 'Full name'), 'Asha Rao');
      await tester.tap(find.text('Save changes'));
      await tester.pumpAndSettle();
      expect(env.profiles.updates, [
        {'full_name': 'Asha Rao'},
      ]);
      expect(find.text('Asha Rao'), findsOneWidget); // back on the profile tab, updated
    });

    testWidgets('validation blocks an empty name and a malformed phone', (tester) async {
      final env = await openEdit(tester);
      await tester.enterText(find.widgetWithText(TextFormField, 'Full name'), '  ');
      await tester.enterText(find.widgetWithText(TextFormField, 'Phone (optional)'), '12345');
      await tester.tap(find.text('Save changes'));
      await tester.pumpAndSettle();
      expect(find.text('Enter your name'), findsOneWidget);
      expect(find.textContaining('international format'), findsOneWidget);
      expect(env.profiles.updates, isEmpty);
    });

    testWidgets('server errors are shown and the form stays open', (tester) async {
      final repo = FakeProfileRepository()
        ..updateError = const ApiException(statusCode: 422, code: 'VALIDATION_ERROR', message: 'Name is not allowed.');
      await openEdit(tester, profiles: repo);
      await tester.enterText(find.widgetWithText(TextFormField, 'Full name'), 'Someone');
      await tester.tap(find.text('Save changes'));
      await tester.pumpAndSettle();
      expect(find.text('Name is not allowed.'), findsOneWidget);
      expect(find.text('Save changes'), findsOneWidget);
    });

    testWidgets('saving without changes just closes', (tester) async {
      final env = await openEdit(tester);
      await tester.tap(find.text('Save changes'));
      await tester.pumpAndSettle();
      expect(env.profiles.updates, isEmpty);
      expect(find.text('Edit profile'), findsOneWidget); // the button on the profile tab
    });
  });

  group('Location and city', () {
    testWidgets('city can be picked manually when location is denied; it is saved and used', (tester) async {
      final env = TestEnv(location: FakeLocationService(current: LocationAccess.denied));
      await env.pump(tester);
      expect(find.text('Select city'), findsOneWidget);

      await tester.tap(find.text('Select city'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Mumbai'));
      await tester.pumpAndSettle();

      expect(find.text('Mumbai'), findsOneWidget);
      expect(env.profiles.preferredCities, ['c-bom']);
      expect(env.venues.queries.last.cityId, 'c-bom');
      expect(env.location.requests, 0); // never prompted for permission
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString(PrefKeys.cityId), 'c-bom');
    });

    testWidgets('saved city is restored on the next launch', (tester) async {
      await TestEnv().pump(tester, prefs: {
        PrefKeys.onboardingDone: true,
        PrefKeys.cityId: 'c-blr',
        PrefKeys.cityName: 'Bengaluru',
      });
      expect(find.text('Bengaluru'), findsWidgets);
    });

    testWidgets('permission already granted: nearby venues appear without a prompt', (tester) async {
      final env = TestEnv(location: FakeLocationService(current: LocationAccess.granted, point: const GeoPoint(12.97, 77.59)));
      await env.pump(tester);
      expect(find.text('Nearby venues'), findsOneWidget);
      expect(env.location.requests, 0);
      final nearby = env.venues.queries.where((q) => q.radiusKm != null).last;
      expect(nearby.lat, 12.97);
      expect(nearby.sort.apiValue, 'distance');
    });

    testWidgets('no location: Home offers to enable it, and Enable asks permission', (tester) async {
      final env = TestEnv(
        location: FakeLocationService(current: LocationAccess.denied, requestResult: LocationAccess.granted, point: const GeoPoint(12.9, 77.5)),
      );
      await env.pump(tester);
      expect(find.text('Venues near you'), findsOneWidget);
      await tester.tap(find.text('Enable'));
      await tester.pumpAndSettle();
      expect(env.location.requests, 1);
      expect(find.text('Nearby venues'), findsOneWidget);
    });

    testWidgets('permanently denied location offers Settings', (tester) async {
      final env = TestEnv(location: FakeLocationService(requestResult: LocationAccess.deniedForever));
      await env.pump(tester);
      await tester.tap(find.text('Enable'));
      await tester.pumpAndSettle();
      expect(find.textContaining('blocked'), findsOneWidget);
      await tester.tap(find.text('Settings'));
      await tester.pump();
      expect(env.location.settingsOpened, 1);
    });

    test('a stored city that no longer exists is dropped', () async {
      SharedPreferences.setMockInitialValues({PrefKeys.cityId: 'gone', PrefKeys.cityName: 'Atlantis'});
      final prefs = await SharedPreferences.getInstance();
      final c = ProviderContainer(overrides: [
        sharedPreferencesProvider.overrideWithValue(prefs),
        venueRepositoryProvider.overrideWithValue(FakeVenueRepository()),
        profileRepositoryProvider.overrideWithValue(FakeProfileRepository()),
        locationServiceProvider.overrideWithValue(FakeLocationService()),
      ]);
      addTearDown(c.dispose);
      c.listen(locationControllerProvider, (_, __) {});
      expect(c.read(locationControllerProvider).city?.name, 'Atlantis'); // optimistic first paint
      await Future<void>.delayed(const Duration(milliseconds: 50));
      expect(c.read(locationControllerProvider).city, isNull);
      expect(prefs.getString(PrefKeys.cityId), isNull);
    });
  });
}
