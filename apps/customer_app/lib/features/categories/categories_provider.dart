import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../shared/models/catalog.dart';
import '../../shared/repositories/venue_repository.dart';

/// Sports categories from `GET /categories` (active, in the admin-defined order).
/// Nothing is hard-coded in the app; icons are chosen by the API's `icon_key`.
final categoriesProvider =
    FutureProvider<List<VenueCategory>>((ref) => ref.watch(venueRepositoryProvider).categories());
