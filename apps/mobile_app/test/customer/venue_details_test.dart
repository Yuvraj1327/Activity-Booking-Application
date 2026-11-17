import 'package:flutter/material.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:zuruv/customer/shared/models/catalog.dart';
import 'package:zuruv/customer/shared/models/venue.dart';

import 'helpers.dart';

VenueDetail detail({String id = 'v1', String? description, bool favorite = false, bool coords = false}) => VenueDetail(
      id: id,
      latitude: coords ? 12.93 : null,
      longitude: coords ? 77.62 : null,
      name: 'Ace Arena',
      cityName: 'Bengaluru',
      addressLine: '80 Feet Rd, Koramangala',
      postalCode: '560034',
      startingPricePaise: 50000,
      ratingAvg: 4.6,
      ratingCount: 12,
      isFavorite: favorite,
      description: description ?? 'Indoor wooden-floor courts with floodlights.',
      contactPhone: '+918012345678',
      categories: const ['badminton'],
      categoryDetails: const [badminton],
      amenities: const [Amenity(id: 'a1', slug: 'parking', name: 'Parking'), Amenity(id: 'a2', slug: 'shower', name: 'Shower')],
    );

void main() {
  Future<TestEnv> openDetails(WidgetTester tester, {Map<String, VenueDetail>? details, FakeVenueRepository? repo}) async {
    final env = TestEnv(venues: repo ?? FakeVenueRepository(details: details ?? {'v1': detail()}));
    await env.pump(tester);
    await tester.tap(find.text('Ace Arena').first);
    await tester.pumpAndSettle();
    return env;
  }

  testWidgets('shows name, rating, address, price, description and amenities', (tester) async {
    await openDetails(tester);
    expect(find.text('Ace Arena'), findsWidgets);
    expect(find.text('4.6'), findsOneWidget);
    expect(find.textContaining('12 reviews'), findsOneWidget);
    expect(find.textContaining('80 Feet Rd, Koramangala, Bengaluru'), findsOneWidget);
    expect(find.textContaining('From ₹500 per hour'), findsOneWidget);
    expect(find.textContaining('Indoor wooden-floor courts'), findsOneWidget);
    await tester.scrollUntilVisible(find.text('Facilities & amenities'), 300, scrollable: find.descendant(of: find.byType(CustomScrollView), matching: find.byType(Scrollable)).first);
    expect(find.text('Parking'), findsOneWidget);
    expect(find.text('Shower'), findsOneWidget);
  });

  testWidgets('Directions opens maps at the venue coordinates, only when it has them', (tester) async {
    final env = await openDetails(tester, details: {'v1': detail(coords: true)});
    await tester.ensureVisible(find.text('Directions'));
    await tester.tap(find.text('Directions'));
    await tester.pumpAndSettle();
    expect(env.directions.opened, [(12.93, 77.62)]);
  });

  testWidgets('no Directions button without coordinates', (tester) async {
    await openDetails(tester);
    expect(find.text('Directions'), findsNothing);
  });

  testWidgets('Directions says so when no maps app can be opened', (tester) async {
    final env = TestEnv(venues: FakeVenueRepository(details: {'v1': detail(coords: true)}));
    env.directions.succeeds = false;
    await env.pump(tester);
    await tester.tap(find.text('Ace Arena').first);
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Directions'));
    await tester.tap(find.text('Directions'));
    await tester.pumpAndSettle();
    expect(find.text('Could not open maps on this device.'), findsOneWidget);
  });

  testWidgets('Book Now opens the slot picker with real availability', (tester) async {
    await openDetails(tester);
    await tester.tap(find.text('Book Now'));
    await tester.pumpAndSettle();
    expect(find.text('Review & book'), findsOneWidget);
    expect(find.text('Court 1'), findsOneWidget);
  });

  testWidgets('a venue with no photo or rating still renders cleanly', (tester) async {
    final bare = const VenueDetail(id: 'v1', name: 'Ace Arena');
    await openDetails(tester, details: {'v1': bare});
    expect(find.text('New'), findsWidgets);
    expect(find.textContaining('No reviews yet'), findsOneWidget);
    expect(find.text('Pricing soon'), findsWidgets);
    expect(find.byIcon(Icons.sports_score_rounded), findsWidgets); // image fallback, not a stock photo
  });

  testWidgets('a venue that was unpublished shows a clear message', (tester) async {
    await openDetails(tester, details: const {}); // list shows it, detail 404s
    expect(find.text('This venue is no longer available'), findsOneWidget);
  });

  testWidgets('detail load failure offers retry', (tester) async {
    final repo = FakeVenueRepository(details: {'v1': detail()})
      ..detailError = const ApiException(statusCode: 0, code: 'NETWORK_ERROR', message: 'offline');
    await openDetails(tester, repo: repo);
    expect(find.text('Try again'), findsOneWidget);
    repo.detailError = null;
    await tester.tap(find.text('Try again'));
    await tester.pumpAndSettle();
    expect(find.text('Book Now'), findsOneWidget);
  });

  testWidgets('favoriting on the detail page shows up in the Favorites tab', (tester) async {
    final env = await openDetails(tester);
    await tester.tap(find.byIcon(Icons.favorite_border_rounded).first);
    await tester.pumpAndSettle();
    expect(env.venues.added, ['v1']);

    await tester.tap(find.byTooltip('Back'));
    await tester.pumpAndSettle();
    await tester.tap(inNavBar('Favorites'));
    await tester.pumpAndSettle();
    expect(find.text('Ace Arena'), findsOneWidget);
    expect(find.text('Baseline Club'), findsNothing);
  });
}
