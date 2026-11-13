import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:go_router/go_router.dart';

import 'package:zuruv/core/constants/tokens.dart';
import 'package:zuruv/customer/shared/widgets/common_widgets.dart';
import 'package:zuruv/customer/features/discovery/venue_list_controller.dart';
import 'package:zuruv/customer/features/favorites/favorites_controller.dart';

class FavoritesScreen extends ConsumerStatefulWidget {
  const FavoritesScreen({super.key});

  @override
  ConsumerState<FavoritesScreen> createState() => _FavoritesScreenState();
}

class _FavoritesScreenState extends ConsumerState<FavoritesScreen> {
  final _scroll = ScrollController();

  @override
  void initState() {
    super.initState();
    _scroll.addListener(() {
      if (_scroll.hasClients && _scroll.position.pixels >= _scroll.position.maxScrollExtent - 400) {
        ref.read(venueListControllerProvider(favoritesQuery).notifier).loadMore();
      }
    });
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(venueListControllerProvider(favoritesQuery));
    final controller = ref.read(venueListControllerProvider(favoritesQuery).notifier);
    final overrides = ref.watch(favoritesControllerProvider);
    // A heart un-tapped on this screen disappears immediately, without waiting for a refetch.
    final items = state.items.where((v) => overrides[v.id] ?? true).toList();

    Widget body;
    if (state.loading && state.items.isEmpty) {
      body = ListView.separated(
        padding: const EdgeInsets.all(Gap.page),
        itemCount: 3,
        separatorBuilder: (_, __) => const SizedBox(height: 20),
        itemBuilder: (_, __) => const VenueCardSkeleton(),
      );
    } else if (state.error != null) {
      body = ErrorView.fromError(state.error!, onRetry: controller.refresh);
    } else if (items.isEmpty && !state.hasMore) {
      body = EmptyState(
        icon: Icons.favorite_border_rounded,
        title: 'No favorites yet',
        message: 'Tap the heart on any venue to save it here.',
        action: FilledButton(
          style: FilledButton.styleFrom(minimumSize: const Size(180, 48)),
          onPressed: () => context.go('/explore'),
          child: const Text('Explore venues'),
        ),
      );
    } else {
      body = RefreshIndicator(
        onRefresh: controller.refresh,
        child: Align(
          alignment: Alignment.topCenter,
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 640),
            child: ListView.separated(
              controller: _scroll,
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.fromLTRB(Gap.page, 8, Gap.page, 24),
              itemCount: items.length + 1,
              separatorBuilder: (_, __) => const SizedBox(height: 16),
              itemBuilder: (context, i) {
                if (i == items.length) {
                  return ListFooter(loading: state.loadingMore, error: state.loadMoreError != null, onRetry: controller.loadMore);
                }
                final venue = items[i];
                return VenueCard(venue: venue, onTap: () => context.push('/venues/${venue.id}'));
              },
            ),
          ),
        ),
      );
    }
    return Scaffold(
      appBar: AppBar(title: Text('Favorites', style: Theme.of(context).textTheme.titleLarge)),
      body: body,
    );
  }
}
