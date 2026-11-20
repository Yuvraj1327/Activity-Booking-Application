import 'package:flutter/material.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:zuruv/owner/features/venue_form/venue_form_screen.dart';

import 'helpers.dart';

Future<void> openVenues(WidgetTester tester, TestEnv env) async {
  await env.pump(tester);
  await tester.tap(inNavBar('Venues'));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('lists only the owner\'s venues with status, rating and price', (tester) async {
    await openVenues(tester, TestEnv());
    expect(find.text('Ace Arena'), findsOneWidget);
    expect(find.text('Draft Court'), findsOneWidget);
    expect(find.text('Published'), findsWidgets);
    expect(find.text('Draft'), findsWidgets);
    expect(find.text('4.6 (12)'), findsOneWidget);
    expect(find.text('From ₹500/hr'), findsWidgets);
  });

  testWidgets('search and status filter go to the API', (tester) async {
    final repo = FakeOwnerRepository();
    await openVenues(tester, TestEnv(repo: repo));
    await tester.enterText(find.byType(TextField), 'ace');
    await tester.pump(const Duration(milliseconds: 600));
    await tester.pumpAndSettle();
    expect(repo.venueQueries.last, 'ace');
    expect(find.text('Draft Court'), findsNothing);

    await tester.enterText(find.byType(TextField), '');
    await tester.pump(const Duration(milliseconds: 600));
    await tester.tap(find.textContaining('Drafts'));
    await tester.pumpAndSettle();
    expect(repo.statusFilters.last, 'draft');
    expect(find.text('Ace Arena'), findsNothing);
    expect(find.text('Draft Court'), findsOneWidget);
  });

  testWidgets('empty states: no venues, and no matches', (tester) async {
    await openVenues(tester, TestEnv(repo: FakeOwnerRepository(venues: [])));
    expect(find.text('No venues yet'), findsOneWidget);
    await tester.enterText(find.byType(TextField), 'zzz');
    await tester.pump(const Duration(milliseconds: 600));
    await tester.pumpAndSettle();
    expect(find.text('No venues match'), findsOneWidget);
  });

  testWidgets('a failed load shows the error and retry recovers', (tester) async {
    final repo = FakeOwnerRepository()..venuesError = Exception('down');
    await openVenues(tester, TestEnv(repo: repo));
    expect(find.text('Try again'), findsOneWidget);
    repo.venuesError = null;
    await tester.tap(find.text('Try again'));
    await tester.pumpAndSettle();
    expect(find.text('Ace Arena'), findsOneWidget);
  });

  testWidgets('add venue: name is required, saving creates a draft and unlocks photos', (tester) async {
    final repo = FakeOwnerRepository();
    await openVenues(tester, TestEnv(repo: repo));
    await tester.tap(find.text('Add venue'));
    await tester.pumpAndSettle();
    expect(find.text('Save the draft first, then add photos.'), findsOneWidget);

    await reveal(tester, find.text('Save draft'));
    await tester.tap(find.text('Save draft'));
    await tester.pumpAndSettle();
    await reveal(tester, find.text('Enter the venue name'), delta: -300);
    expect(find.text('Enter the venue name'), findsOneWidget);
    expect(repo.created, isEmpty);

    await tester.enterText(find.widgetWithText(TextFormField, 'Venue name'), 'Court One');
    await tester.enterText(find.widgetWithText(TextFormField, 'Starting price per hour (₹, optional)'), '600');
    await tester.tap(find.text('Badminton'));
    await tester.pump();
    await reveal(tester, find.text('Save draft'));
    await tester.tap(find.text('Save draft'));
    await tester.pumpAndSettle();
    expect(repo.created.single.name, 'Court One');
    expect(repo.created.single.startingPricePaise, 60000);
    expect(repo.created.single.categoryIds, ['k1']);
    await reveal(tester, find.text('Save changes'));
    expect(find.text('Save changes'), findsOneWidget); // now editing the saved draft
    await reveal(tester, find.text('Add photo'), delta: -300);
    expect(find.text('Add photo'), findsOneWidget);
  });

  testWidgets('latitude and longitude must come as a pair', (tester) async {
    final repo = FakeOwnerRepository();
    await openVenues(tester, TestEnv(repo: repo));
    await tester.tap(find.text('Add venue'));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextFormField, 'Venue name'), 'Court One');
    await reveal(tester, find.widgetWithText(TextFormField, 'Latitude'));
    await tester.enterText(find.widgetWithText(TextFormField, 'Latitude'), '12.9');
    await reveal(tester, find.text('Save draft'));
    await tester.tap(find.text('Save draft'));
    await tester.pumpAndSettle();
    await reveal(tester, find.text('Enter longitude too'), delta: -200);
    expect(find.text('Enter longitude too'), findsOneWidget);
    expect(repo.created, isEmpty);
    await tester.enterText(find.widgetWithText(TextFormField, 'Longitude'), '200');
    await reveal(tester, find.text('Save draft'));
    await tester.tap(find.text('Save draft'));
    await tester.pumpAndSettle();
    await reveal(tester, find.text('Between -180 and 180'), delta: -200);
    expect(find.text('Between -180 and 180'), findsOneWidget);
  });

  testWidgets('address search fills address, postal code and coordinates', (tester) async {
    final repo = FakeOwnerRepository();
    await openVenues(tester, TestEnv(repo: repo));
    await tester.tap(find.text('Add venue'));
    await tester.pumpAndSettle();
    await reveal(tester, find.text('Search address'));
    await tester.tap(find.text('Search address'));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextField, 'Venue address or landmark'), 'Ace Arena');
    await tester.tap(find.byTooltip('Search'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Ace Arena Road, Pune'));
    await tester.pumpAndSettle();
    expect(find.text('Ace Arena Road, Pune 411001'), findsOneWidget);
    expect(find.text('18.52'), findsOneWidget);
    expect(find.text('73.85'), findsOneWidget);
  });

  testWidgets('address search says so when the server has no Google key', (tester) async {
    final repo = FakeOwnerRepository()
      ..placesFail = const PlacesFail(ApiException(
          statusCode: 503, code: 'PLACES_NOT_CONFIGURED', message: 'Address search is not configured yet.'));
    await openVenues(tester, TestEnv(repo: repo));
    await tester.tap(find.text('Add venue'));
    await tester.pumpAndSettle();
    await reveal(tester, find.text('Search address'));
    await tester.tap(find.text('Search address'));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextField, 'Venue address or landmark'), 'Ace');
    await tester.tap(find.byTooltip('Search'));
    await tester.pumpAndSettle();
    expect(find.text('Address search is not configured yet.'), findsOneWidget);
  });

  testWidgets('edit venue: loads values, sends changes, clears emptied optional fields', (tester) async {
    final repo = FakeOwnerRepository();
    await openVenues(tester, TestEnv(repo: repo));
    await tester.tap(find.text('Ace Arena'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Edit venue'));
    await tester.pumpAndSettle();
    expect(find.widgetWithText(TextFormField, 'Venue name'), findsOneWidget);
    expect(tester.widget<TextFormField>(find.widgetWithText(TextFormField, 'Venue name')).controller!.text, 'Ace Arena');
    await reveal(tester, find.widgetWithText(TextFormField, 'Starting price per hour (₹, optional)'));
    expect(tester.widget<TextFormField>(find.widgetWithText(TextFormField, 'Starting price per hour (₹, optional)')).controller!.text, '500');
    await reveal(tester, find.widgetWithText(TextFormField, 'Venue name'), delta: -300);

    await tester.enterText(find.widgetWithText(TextFormField, 'Venue name'), 'Ace Arena 2');
    await reveal(tester, find.widgetWithText(TextFormField, 'Starting price per hour (₹, optional)'));
    await tester.enterText(find.widgetWithText(TextFormField, 'Starting price per hour (₹, optional)'), '');
    await reveal(tester, find.text('Save changes'));
    await tester.tap(find.text('Save changes'));
    await tester.pumpAndSettle();
    final sent = repo.updated['v1']!.toJson();
    expect(sent['name'], 'Ace Arena 2');
    expect(sent.containsKey('starting_price_paise'), isTrue);
    expect(sent['starting_price_paise'], isNull);
  });

  testWidgets('photos: upload, preview, set cover, remove, and early rejection of bad files', (tester) async {
    final repo = FakeOwnerRepository();
    final picker = FakePhotoPicker(PickedPhoto(name: 'court.jpg', bytes: List.filled(100, 1)));
    await openVenues(tester, TestEnv(repo: repo, picker: picker));
    await tester.tap(find.text('Ace Arena'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Edit venue'));
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.byKey(const ValueKey('add-photo')), 300, scrollable: find.byType(Scrollable).first);

    await tester.tap(find.byKey(const ValueKey('add-photo')));
    await tester.pumpAndSettle();
    expect(repo.uploads, ['court.jpg']);
    expect(find.text('Cover'), findsOneWidget);

    picker.photo = PickedPhoto(name: 'second.png', bytes: List.filled(100, 1));
    await tester.tap(find.byKey(const ValueKey('add-photo')));
    await tester.pumpAndSettle();
    expect(repo.uploads.length, 2);

    await tester.tap(find.byKey(const ValueKey('photo-img-2')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Set as cover'));
    await tester.pumpAndSettle();
    expect(repo.coverSet, ['img-2']);

    await tester.tap(find.byKey(const ValueKey('photo-img-1')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Remove photo'));
    await tester.pumpAndSettle();
    expect(repo.removedImages, ['img-1']);

    picker.photo = PickedPhoto(name: 'notes.gif', bytes: List.filled(10, 1));
    await tester.tap(find.byKey(const ValueKey('add-photo')));
    await tester.pumpAndSettle();
    await reveal(tester, find.text('Choose a JPG, PNG or WebP image.'), delta: -300);
    expect(find.text('Choose a JPG, PNG or WebP image.'), findsOneWidget);
    await reveal(tester, find.byKey(const ValueKey('add-photo')));

    picker.photo = PickedPhoto(name: 'huge.jpg', bytes: List.filled(5 * 1024 * 1024 + 1, 1));
    await tester.tap(find.byKey(const ValueKey('add-photo')));
    await tester.pumpAndSettle();
    await reveal(tester, find.text('That image is larger than 5 MB. Choose a smaller one.'), delta: -300);
    expect(find.text('That image is larger than 5 MB. Choose a smaller one.'), findsOneWidget);
    expect(repo.uploads.length, 2); // neither bad file was sent
  });

  testWidgets('venue page: publish is blocked until the listing is complete, then works', (tester) async {
    final repo = FakeOwnerRepository()..publishBlockers = ['Choose a city.', 'Choose at least one sport category.'];
    await openVenues(tester, TestEnv(repo: repo));
    await tester.tap(find.text('Draft Court'));
    await tester.pumpAndSettle();
    expect(find.text('Before you can publish'), findsOneWidget);
    expect(find.text('• Choose a city.'), findsOneWidget);
    final publish = tester.widget<FilledButton>(find.widgetWithText(FilledButton, 'Publish venue'));
    expect(publish.onPressed, isNull);

    repo.publishBlockers = const [];
    await tester.pageBack();
    await tester.pumpAndSettle();
    await tester.tap(find.text('Draft Court'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Publish venue'));
    await tester.pumpAndSettle();
    expect(repo.published, ['v2']);
  });

  testWidgets('venue page: take offline, and delete asks first', (tester) async {
    final repo = FakeOwnerRepository();
    await openVenues(tester, TestEnv(repo: repo));
    await tester.tap(find.text('Ace Arena'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Take offline'));
    await tester.pumpAndSettle();
    expect(repo.unpublished, ['v1']);

    await tester.scrollUntilVisible(find.text('Delete venue'), 200, scrollable: find.byType(Scrollable).first);
    await tester.tap(find.text('Delete venue'));
    await tester.pumpAndSettle();
    expect(find.text('Delete this venue?'), findsOneWidget);
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();
    expect(repo.deleted, isEmpty);

    await tester.tap(find.text('Delete venue'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(TextButton, 'Delete'));
    await tester.pumpAndSettle();
    expect(repo.deleted, ['v1']);
    expect(find.text('Ace Arena'), findsNothing);
  });

  testWidgets('another owner\'s or missing venue shows not found, not data', (tester) async {
    await openVenues(tester, TestEnv());
    // Same response the API gives for a venue that belongs to someone else.
    final context = tester.element(find.byType(Scaffold).first);
    context.push('/owner/venues/someone-elses');
    await tester.pumpAndSettle();
    expect(find.text('Venue not found.'), findsOneWidget);
  });
}
