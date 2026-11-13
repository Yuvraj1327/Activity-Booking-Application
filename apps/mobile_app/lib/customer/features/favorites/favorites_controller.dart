import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';

import 'package:zuruv/customer/shared/models/venue.dart';
import 'package:zuruv/customer/shared/repositories/venue_repository.dart';
import 'package:zuruv/customer/features/discovery/venue_list_controller.dart';

/// The query behind the Favorites tab (also used to refresh it after a change).
const favoritesQuery = VenueQuery(favoritesOnly: true);

/// Favorite flags the user changed in this session, keyed by venue id. Lists and the detail
/// screen show `overrides[id] ?? serverFlag`, so a heart tapped anywhere updates everywhere at
/// once, with no list refetch. Reset when a different account signs in.
class FavoritesController extends Notifier<Map<String, bool>> {
  @override
  Map<String, bool> build() {
    ref.watch(authControllerProvider.select((s) => s is Authenticated ? s.profile.id : null));
    return const {};
  }

  bool isFavorite(VenueSummary venue) => state[venue.id] ?? venue.isFavorite;

  /// Optimistic toggle. Returns false (and restores the previous value) when the API call fails.
  Future<bool> toggle(VenueSummary venue) async {
    final previous = isFavorite(venue);
    final next = !previous;
    state = {...state, venue.id: next};
    try {
      final repo = ref.read(venueRepositoryProvider);
      if (next) {
        await repo.addFavorite(venue.id);
        // A newly added venue is not in the loaded favorites list yet.
        ref.invalidate(venueListControllerProvider(favoritesQuery));
      } else {
        await repo.removeFavorite(venue.id);
      }
      return true;
    } catch (_) {
      state = {...state, venue.id: previous};
      return false;
    }
  }
}

final favoritesControllerProvider = NotifierProvider<FavoritesController, Map<String, bool>>(FavoritesController.new);
