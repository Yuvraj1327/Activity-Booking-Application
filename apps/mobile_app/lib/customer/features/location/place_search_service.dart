import 'package:flutter_riverpod/flutter_riverpod.dart';

/// A suggestion from an address / place autocomplete.
class PlaceSuggestion {
  const PlaceSuggestion({required this.placeId, required this.description});
  final String placeId;
  final String description;
}

/// Google Maps / Places integration point (PREPARED, not enabled).
///
/// A Google API key must never ship inside the app. The intended implementation calls a ZURUV
/// backend endpoint (for example `GET /places/autocomplete?q=`) that holds the key server-side,
/// or uses a key restricted to this app's bundle id / package name + SHA-1 in Google Cloud.
/// Until that endpoint exists the app uses [UnconfiguredPlaceSearchService]; city selection and
/// device location work without it. See docs/STEP_4_REPORT.md.
abstract class PlaceSearchService {
  bool get isAvailable;
  Future<List<PlaceSuggestion>> autocomplete(String input);
}

class UnconfiguredPlaceSearchService implements PlaceSearchService {
  const UnconfiguredPlaceSearchService();

  @override
  bool get isAvailable => false;

  @override
  Future<List<PlaceSuggestion>> autocomplete(String input) async => const [];
}

final placeSearchServiceProvider = Provider<PlaceSearchService>((ref) => const UnconfiguredPlaceSearchService());
