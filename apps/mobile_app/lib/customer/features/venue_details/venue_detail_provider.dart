import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:zuruv/customer/shared/models/venue.dart';
import 'package:zuruv/customer/shared/repositories/venue_repository.dart';
import 'package:zuruv/customer/features/location/location_controller.dart';

/// One venue's full details. Includes the distance when the device location is known.
final venueDetailProvider = FutureProvider.autoDispose.family<VenueDetail, String>((ref, id) {
  final point = ref.watch(locationControllerProvider.select((s) => s.point));
  return ref.watch(venueRepositoryProvider).venue(
        id,
        lat: point == null ? null : (point.lat * 100).roundToDouble() / 100,
        lng: point == null ? null : (point.lng * 100).roundToDouble() / 100,
      );
});
