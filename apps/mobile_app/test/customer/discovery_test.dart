import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:zuruv/customer/features/discovery/venue_list_controller.dart';
import 'package:zuruv/customer/shared/models/catalog.dart';
import 'package:zuruv/customer/shared/models/venue.dart';
import 'package:zuruv/customer/shared/repositories/venue_repository.dart';

import 'helpers.dart';

void main() {
  group('Home', () {
    testWidgets('shows categories and popular venues from the API', (tester) async {
      await TestEnv().pump(tester);
      expect(find.text('Badminton'), findsOneWidget);
      expect(find.text('Tennis'), findsOneWidget);
      expect(find.text('Popular venues'), findsOneWidget);
      expect(find.text('Ace Arena'), findsOneWidget);
      expect(find.textContaining('₹500', findRichText: true), findsWidgets); // 50000 paise per hour (rich text: price + /hr)
    });

    testWidgets('"More" appears only with more than 8 categories and lists them all', (tester) async {
      final many = [for (var i = 0; i < 10; i++) VenueCategoryFixture.make(i)];
      await TestEnv(venues: FakeVenueRepository(categoryList: many)).pump(tester);
      expect(find.text('More'), findsOneWidget);
      await tester.tap(find.text('More'));
      await tester.pumpAndSettle();
      expect(find.text('All sports'), findsOneWidget);
      expect(find.text('Sport 9'), findsOneWidget);
    });

    testWidgets('tapping a category opens that sport and filters by it', (tester) async {
      final env = TestEnv(
        venues: FakeVenueRepository(venues: [
          venue('v1', 'Ace Arena'),
          venue('v2', 'Court Tennis Club', categories: const ['tennis']),
        ]),
      );
      await env.pump(tester);
      await tester.tap(find.text('Tennis'));
      await tester.pumpAndSettle();
      expect(env.venues.queries.last.category, 'tennis');
      expect(find.text('Court Tennis Club'), findsOneWidget);
      expect(find.text('Ace Arena'), findsNothing);
    });

    testWidgets('API failure shows a retry that recovers', (tester) async {
      final repo = FakeVenueRepository()..venuesError = const ApiException(statusCode: 0, code: 'NETWORK_ERROR', message: 'offline');
      await TestEnv(venues: repo).pump(tester);
      expect(find.text('Try again'), findsWidgets);

      repo.venuesError = null;
      await tester.tap(find.text('Try again').first);
      await tester.pumpAndSettle();
      expect(find.text('Ace Arena'), findsOneWidget);
    });

    testWidgets('empty city shows a friendly message, not a blank screen', (tester) async {
      await TestEnv(venues: FakeVenueRepository(venues: const [])).pump(tester);
      expect(find.text('No venues are listed yet.'), findsOneWidget);
    });

    testWidgets('tapping the heart is optimistic and calls the API', (tester) async {
      final env = TestEnv();
      await env.pump(tester);
      await tester.tap(find.byIcon(Icons.favorite_border_rounded).first);
      await tester.pump();
      expect(find.byIcon(Icons.favorite_rounded), findsOneWidget);
      await tester.pumpAndSettle();
      expect(env.venues.added, ['v1']);
    });

    testWidgets('a failed favorite is rolled back and explained', (tester) async {
      final repo = FakeVenueRepository()..failFavorites = true;
      await TestEnv(venues: repo).pump(tester);
      await tester.tap(find.byIcon(Icons.favorite_border_rounded).first);
      await tester.pumpAndSettle();
      expect(find.byIcon(Icons.favorite_rounded), findsNothing);
      expect(find.textContaining("Couldn't update your favorites"), findsOneWidget);
    });
  });

  group('Explore', () {
    Future<TestEnv> openExplore(WidgetTester tester, {FakeVenueRepository? repo}) async {
      final env = TestEnv(venues: repo);
      await env.pump(tester);
      await tester.tap(inNavBar('Explore'));
      await tester.pumpAndSettle();
      return env;
    }

    testWidgets('lists venues and filters by search text after a pause', (tester) async {
      final env = await openExplore(tester);
      expect(find.text('Baseline Club'), findsOneWidget);

      await tester.enterText(find.byType(TextField), 'base');
      await tester.pump(const Duration(milliseconds: 200));
      expect(env.venues.queries.where((q) => q.text == 'base'), isEmpty); // still debouncing
      await tester.pump(const Duration(milliseconds: 400));
      await tester.pumpAndSettle();
      expect(env.venues.queries.last.text, 'base');
      expect(find.text('Ace Arena'), findsNothing);
      expect(find.text('Baseline Club'), findsOneWidget);
    });

    testWidgets('no match shows an empty state with Clear filters', (tester) async {
      await openExplore(tester);
      await tester.enterText(find.byType(TextField), 'zzz');
      await tester.pump(const Duration(milliseconds: 600));
      await tester.pumpAndSettle();
      expect(find.text('No venues found'), findsOneWidget);
      await tester.tap(find.text('Clear filters'));
      await tester.pumpAndSettle();
      expect(find.text('Ace Arena'), findsOneWidget);
    });

    testWidgets('price filter sends min/max in paise', (tester) async {
      final env = await openExplore(tester);
      await tester.tap(find.text('Price'));
      await tester.pumpAndSettle();
      expect(find.text('Price per hour'), findsOneWidget);
      await tester.tap(find.text('Apply')); // untouched slider = no limits
      await tester.pumpAndSettle();
      expect(env.venues.queries.last.minPricePaise, isNull);
      expect(env.venues.queries.last.maxPricePaise, isNull);
    });

    testWidgets('"Today" asks the backend for venues with a slot left today', (tester) async {
      final env = await openExplore(tester);
      expect(env.venues.queries.last.availableToday, isFalse);
      await tester.tap(find.widgetWithText(FilterChip, 'Today'));
      await tester.pumpAndSettle();
      expect(env.venues.queries.last.availableToday, isTrue);
      await tester.tap(find.widgetWithText(FilterChip, 'Today'));
      await tester.pumpAndSettle();
      expect(env.venues.queries.last.availableToday, isFalse);
    });

    testWidgets('Near Me with permission denied keeps the app usable and explains why', (tester) async {
      final env = await openExplore(tester);
      await tester.tap(find.text('Near Me'));
      await tester.pumpAndSettle();
      expect(env.location.requests, 1);
      expect(find.textContaining('permission was denied'), findsOneWidget);
      expect(find.text('Ace Arena'), findsOneWidget); // list still works with no location
      expect(env.venues.queries.last.radiusKm, isNull);
    });
  });

  group('VenueListController', () {
    ProviderContainer make(FakeVenueRepository repo) {
      final c = ProviderContainer(overrides: [venueRepositoryProvider.overrideWithValue(repo)]);
      addTearDown(c.dispose);
      return c;
    }

    Future<void> settle() => Future<void>.delayed(Duration.zero);

    test('paginates and de-duplicates', () async {
      final repo = FakeVenueRepository(venues: [for (var i = 0; i < 5; i++) venue('v$i', 'Venue $i')]);
      final c = make(repo);
      const q = VenueQuery(pageSize: 2);
      c.listen(venueListControllerProvider(q), (_, __) {});
      await settle();
      await settle();
      var s = c.read(venueListControllerProvider(q));
      expect(s.items.map((v) => v.id), ['v0', 'v1']);
      expect(s.hasMore, isTrue);

      await c.read(venueListControllerProvider(q).notifier).loadMore();
      await c.read(venueListControllerProvider(q).notifier).loadMore();
      s = c.read(venueListControllerProvider(q));
      expect(s.items.length, 5);
      expect(s.hasMore, isFalse);

      await c.read(venueListControllerProvider(q).notifier).loadMore(); // no more: a no-op
      expect(c.read(venueListControllerProvider(q)).items.length, 5);
    });

    test('first-page failure sets error; refresh recovers', () async {
      final repo = FakeVenueRepository()..venuesError = const ApiException(statusCode: 500, code: 'X', message: 'boom');
      final c = make(repo);
      const q = VenueQuery();
      c.listen(venueListControllerProvider(q), (_, __) {});
      await settle();
      await settle();
      expect(c.read(venueListControllerProvider(q)).error, isA<ApiException>());

      repo.venuesError = null;
      await c.read(venueListControllerProvider(q).notifier).refresh();
      final s = c.read(venueListControllerProvider(q));
      expect(s.error, isNull);
      expect(s.items, isNotEmpty);
    });
  });
}

class VenueCategoryFixture {
  static VenueCategory make(int i) => VenueCategory(id: 'k$i', slug: 'sport-$i', name: 'Sport $i');
}
