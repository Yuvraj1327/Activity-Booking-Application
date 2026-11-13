import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:zuruv/core/config/app_config.dart';
import 'package:zuruv/customer/shared/models/venue.dart';
import 'package:zuruv/customer/features/location/location_controller.dart';

double _round(double v) => (v * 100).roundToDouble() / 100; // ~1 km, avoids refetching on GPS jitter

/// Popular venues in the selected city (all cities until one is chosen).
final homePopularQueryProvider = Provider<VenueQuery>((ref) {
  final cityId = ref.watch(locationControllerProvider.select((s) => s.city?.id));
  return VenueQuery(cityId: cityId, sort: VenueSort.popular, pageSize: AppConfig.homeSectionSize);
});

/// Nearest venues, only when the device location is available.
final homeNearbyQueryProvider = Provider<VenueQuery?>((ref) {
  final point = ref.watch(locationControllerProvider.select((s) => s.point));
  if (point == null) return null;
  return VenueQuery(
    lat: _round(point.lat),
    lng: _round(point.lng),
    radiusKm: AppConfig.nearbyRadiusKm,
    sort: VenueSort.distance,
    pageSize: AppConfig.homeSectionSize,
  );
});

/// Bumped to ask the Explore tab to focus its search field (Home search bar tap).
final exploreFocusRequestProvider = StateProvider<int>((ref) => 0);
