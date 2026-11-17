import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:zuruv/core/maps/location_picker_screen.dart';
import 'package:zuruv/core/maps/maps_config.dart';
import 'package:zuruv/customer/features/map/venue_location_map.dart';

void main() {
  test('maps are unavailable without a configured key', () {
    expect(MapsConfig.mapsAvailable, isFalse);
    expect(MapsConfig.placesKey, isEmpty);
  });

  testWidgets('venue map renders nothing when maps are unavailable', (tester) async {
    await tester.pumpWidget(const ProviderScope(
      child: MaterialApp(home: VenueLocationMap(name: 'Ace', latitude: 12.9, longitude: 77.6)),
    ));
    expect(find.byType(SizedBox), findsWidgets);
    expect(find.text('Ace'), findsNothing);
  });

  testWidgets('location picker shows a manual-entry fallback without a key', (tester) async {
    await tester.pumpWidget(const ProviderScope(child: MaterialApp(home: LocationPickerScreen())));
    await tester.pump();
    expect(find.textContaining('Maps are not configured'), findsOneWidget);
    expect(find.text('Use this location'), findsNothing);
  });
}
