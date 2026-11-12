import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../shared/models/venue.dart';
import '../../shared/repositories/venue_repository.dart';

class VenueListState {
  const VenueListState({
    this.items = const [],
    this.loading = false,
    this.loadingMore = false,
    this.error,
    this.loadMoreError,
    this.hasMore = false,
  });

  final List<VenueSummary> items;

  /// First page in flight.
  final bool loading;
  final bool loadingMore;

  /// First page failed (shows a full-screen retry).
  final Object? error;

  /// A later page failed (shows an inline retry; the list is kept).
  final Object? loadMoreError;
  final bool hasMore;

  bool get isEmpty => !loading && error == null && items.isEmpty;
}

/// One paginated list of venues for a [VenueQuery] (home sections, explore, category, favorites).
/// Auto-disposed, so leaving a screen frees it; the shell keeps tab screens alive.
class VenueListController extends AutoDisposeFamilyNotifier<VenueListState, VenueQuery> {
  CancelToken? _cancel;
  bool _disposed = false;
  int _generation = 0;

  @override
  VenueListState build(VenueQuery arg) {
    ref.onDispose(() {
      _disposed = true;
      _cancel?.cancel();
    });
    Future.microtask(_loadFirst);
    return const VenueListState(loading: true);
  }

  VenueRepository get _repo => ref.read(venueRepositoryProvider);

  Future<void> refresh() async {
    state = VenueListState(items: state.items, loading: true, hasMore: state.hasMore);
    await _loadFirst();
  }

  Future<void> _loadFirst() async {
    _cancel?.cancel();
    final cancel = _cancel = CancelToken();
    final generation = ++_generation;
    try {
      final page = await _repo.venues(arg, offset: 0, cancelToken: cancel);
      if (_disposed || generation != _generation) return;
      state = VenueListState(items: page.items, hasMore: page.hasMore);
    } catch (e) {
      if (_disposed || generation != _generation) return;
      state = VenueListState(error: e);
    }
  }

  Future<void> loadMore() async {
    final current = state;
    if (current.loading || current.loadingMore || !current.hasMore || current.error != null) return;
    state = VenueListState(items: current.items, loadingMore: true, hasMore: true);
    final generation = _generation;
    try {
      final page = await _repo.venues(arg, offset: current.items.length);
      if (_disposed || generation != _generation) return;
      // De-duplicate in case rows shifted between requests.
      final seen = current.items.map((v) => v.id).toSet();
      final merged = [...current.items, ...page.items.where((v) => !seen.contains(v.id))];
      state = VenueListState(items: merged, hasMore: page.hasMore);
    } catch (e) {
      if (_disposed || generation != _generation) return;
      state = VenueListState(items: current.items, hasMore: true, loadMoreError: e);
    }
  }
}

final venueListControllerProvider =
    NotifierProvider.autoDispose.family<VenueListController, VenueListState, VenueQuery>(VenueListController.new);
