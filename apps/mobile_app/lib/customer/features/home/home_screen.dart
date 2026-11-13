import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:go_router/go_router.dart';

import 'package:zuruv/customer/features/notifications/notifications_screen.dart';
import 'package:zuruv/core/constants/tokens.dart';
import 'package:zuruv/core/network/api_helpers.dart';
import 'package:zuruv/customer/shared/models/catalog.dart';
import 'package:zuruv/customer/shared/models/venue.dart';
import 'package:zuruv/customer/shared/widgets/category_icons.dart';
import 'package:zuruv/customer/shared/widgets/common_widgets.dart';
import 'package:zuruv/customer/shared/widgets/z_network_image.dart';
import 'package:zuruv/customer/features/categories/categories_provider.dart';
import 'package:zuruv/customer/features/discovery/venue_list_controller.dart';
import 'package:zuruv/customer/features/location/location_controller.dart';
import 'package:zuruv/customer/features/location/location_sheet.dart';
import 'package:zuruv/customer/features/home/home_providers.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final auth = ref.watch(authControllerProvider);
    final firstName = auth is Authenticated ? auth.profile.fullName.split(' ').first : '';
    final city = ref.watch(locationControllerProvider.select((s) => s.city));
    final popularQuery = ref.watch(homePopularQueryProvider);

    Future<void> refresh() async {
      ref.invalidate(categoriesProvider);
      await ref.read(venueListControllerProvider(popularQuery).notifier).refresh();
      final nearby = ref.read(homeNearbyQueryProvider);
      if (nearby != null) await ref.read(venueListControllerProvider(nearby).notifier).refresh();
    }

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: RefreshIndicator(
          onRefresh: refresh,
          child: ListView(
            padding: const EdgeInsets.only(bottom: 24),
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(Gap.page, 12, Gap.page - 6, 0),
                child: Row(
                  children: [
                    Expanded(
                      child: InkWell(
                        borderRadius: BorderRadius.circular(12),
                        onTap: () => showCitySheet(context),
                        child: Padding(
                          padding: const EdgeInsets.symmetric(vertical: 4, horizontal: 2),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('Your city', style: theme.textTheme.bodySmall),
                              Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Icon(Icons.place_rounded, size: 18, color: theme.colorScheme.primary),
                                  const SizedBox(width: 4),
                                  Flexible(
                                    child: Text(
                                      city?.name ?? 'Select city',
                                      style: theme.textTheme.titleMedium,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                  const Icon(Icons.keyboard_arrow_down_rounded),
                                ],
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                    IconButton(
                      tooltip: 'Notifications',
                      onPressed: () => context.push('/notifications'),
                      icon: Badge(
                        isLabelVisible: (ref.watch(unreadCountProvider).valueOrNull ?? 0) > 0,
                        label: Text('${ref.watch(unreadCountProvider).valueOrNull ?? 0}'),
                        child: const Icon(Icons.notifications_none_rounded, size: 26),
                      ),
                    ),
                  ],
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(Gap.page, 12, Gap.page, 0),
                child: Text(
                  firstName.isEmpty ? 'Where do you want to play?' : 'Hi $firstName, where do you want to play?',
                  style: theme.textTheme.headlineMedium,
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(Gap.page, 16, Gap.page, 0),
                child: _SearchBarButton(
                  onTap: () {
                    ref.read(exploreFocusRequestProvider.notifier).state++;
                    context.go('/explore');
                  },
                ),
              ),
              const SizedBox(height: 20),
              const _CategoryGrid(),
              const SizedBox(height: 24),
              SectionHeader(title: 'Popular venues', onSeeAll: () => context.go('/explore')),
              const SizedBox(height: 8),
              _VenueCarousel(query: popularQuery, emptyMessage: city == null ? 'No venues are listed yet.' : 'No venues in ${city.name} yet.'),
              const SizedBox(height: 24),
              const _NearbySection(),
            ],
          ),
        ),
      ),
    );
  }
}

class _SearchBarButton extends StatelessWidget {
  const _SearchBarButton({required this.onTap});
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: 'Search venues',
      child: InkWell(
        borderRadius: BorderRadius.circular(Radii.button),
        onTap: onTap,
        child: Container(
          height: 52,
          padding: const EdgeInsets.symmetric(horizontal: 16),
          decoration: BoxDecoration(
            color: ZuruvColors.primaryTint,
            borderRadius: BorderRadius.circular(Radii.button),
          ),
          child: Row(
            children: [
              Icon(Icons.search_rounded, color: Theme.of(context).colorScheme.primary),
              const SizedBox(width: 10),
              Text('Search venues or sports', style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: ZuruvColors.textSecondary)),
            ],
          ),
        ),
      ),
    );
  }
}

class _CategoryGrid extends ConsumerWidget {
  const _CategoryGrid();

  static const int _maxShown = 7; // + "More" makes a 4 x 2 grid

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final categories = ref.watch(categoriesProvider);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: Gap.page),
      child: categories.when(
        loading: () => const _CategorySkeleton(),
        error: (e, _) => Row(
          children: [
            Expanded(child: Text(errorMessage(e), style: Theme.of(context).textTheme.bodySmall)),
            TextButton(onPressed: () => ref.invalidate(categoriesProvider), child: const Text('Retry')),
          ],
        ),
        data: (list) {
          if (list.isEmpty) return const SizedBox.shrink();
          final shown = list.take(list.length > _maxShown + 1 ? _maxShown : list.length).toList();
          final hasMore = list.length > shown.length;
          final tiles = <Widget>[
            for (final c in shown)
              _CategoryTile(
                icon: categoryIcon(c.iconKey, slug: c.slug),
                label: c.name,
                onTap: () => context.push('/category/${c.slug}'),
              ),
            if (hasMore)
              _CategoryTile(
                icon: Icons.grid_view_rounded,
                label: 'More',
                onTap: () => _showAllCategories(context, list),
              ),
          ];
          return GridView.count(
            crossAxisCount: 4,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            mainAxisSpacing: 14,
            crossAxisSpacing: 8,
            childAspectRatio: 0.82,
            children: tiles,
          );
        },
      ),
    );
  }

  void _showAllCategories(BuildContext context, List<VenueCategory> all) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (sheetContext) => Padding(
        padding: const EdgeInsets.fromLTRB(Gap.page, 0, Gap.page, 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('All sports', style: Theme.of(sheetContext).textTheme.titleLarge),
            const SizedBox(height: 16),
            Flexible(
              child: GridView.count(
                crossAxisCount: 4,
                shrinkWrap: true,
                mainAxisSpacing: 14,
                crossAxisSpacing: 8,
                childAspectRatio: 0.82,
                children: [
                  for (final c in all)
                    _CategoryTile(
                      icon: categoryIcon(c.iconKey, slug: c.slug),
                      label: c.name,
                      onTap: () {
                        Navigator.of(sheetContext).pop();
                        context.push('/category/${c.slug}');
                      },
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _CategoryTile extends StatelessWidget {
  const _CategoryTile({required this.icon, required this.label, required this.onTap});
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Semantics(
      button: true,
      label: label,
      child: InkWell(
        borderRadius: BorderRadius.circular(Radii.card),
        onTap: onTap,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.start,
          children: [
            Container(
              width: 60,
              height: 60,
              decoration: BoxDecoration(color: ZuruvColors.primaryTint, borderRadius: BorderRadius.circular(20)),
              child: Icon(icon, color: theme.colorScheme.primary, size: 28),
            ),
            const SizedBox(height: 8),
            Text(label, style: theme.textTheme.bodySmall?.copyWith(color: ZuruvColors.text, fontWeight: FontWeight.w500), maxLines: 1, overflow: TextOverflow.ellipsis, textAlign: TextAlign.center),
          ],
        ),
      ),
    );
  }
}

class _CategorySkeleton extends StatelessWidget {
  const _CategorySkeleton();

  @override
  Widget build(BuildContext context) {
    return GridView.count(
      crossAxisCount: 4,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      mainAxisSpacing: 14,
      crossAxisSpacing: 8,
      childAspectRatio: 0.82,
      children: List.generate(8, (_) => const Column(children: [ShimmerBox(height: 60, width: 60, radius: 20), SizedBox(height: 8), ShimmerBox(height: 10, width: 44, radius: 5)])),
    );
  }
}

class _VenueCarousel extends ConsumerWidget {
  const _VenueCarousel({required this.query, required this.emptyMessage});

  final VenueQuery query;
  final String emptyMessage;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(venueListControllerProvider(query));
    final controller = ref.read(venueListControllerProvider(query).notifier);

    if (state.loading && state.items.isEmpty) {
      return SizedBox(
        height: 220,
        child: ListView.separated(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: Gap.page),
          itemCount: 3,
          separatorBuilder: (_, __) => const SizedBox(width: 14),
          itemBuilder: (_, __) => const SizedBox(width: 232, child: VenueCardSkeleton()),
        ),
      );
    }
    if (state.error != null) {
      return Padding(
        padding: const EdgeInsets.symmetric(horizontal: Gap.page),
        child: ErrorView.fromError(state.error!, onRetry: controller.refresh),
      );
    }
    if (state.items.isEmpty) {
      return Padding(
        padding: const EdgeInsets.symmetric(horizontal: Gap.page, vertical: 8),
        child: Text(emptyMessage, style: Theme.of(context).textTheme.bodySmall),
      );
    }
    return SizedBox(
      height: 292,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: Gap.page),
        itemCount: state.items.length,
        separatorBuilder: (_, __) => const SizedBox(width: 14),
        itemBuilder: (context, i) {
          final venue = state.items[i];
          return VenueCarouselCard(venue: venue, onTap: () => context.push('/venues/${venue.id}'));
        },
      ),
    );
  }
}

class _NearbySection extends ConsumerWidget {
  const _NearbySection();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final nearbyQuery = ref.watch(homeNearbyQueryProvider);
    final location = ref.watch(locationControllerProvider);

    if (nearbyQuery == null) {
      return Padding(
        padding: const EdgeInsets.symmetric(horizontal: Gap.page),
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(color: ZuruvColors.primaryTint, borderRadius: BorderRadius.circular(Radii.card)),
          child: Row(
            children: [
              Icon(Icons.near_me_rounded, color: theme.colorScheme.primary, size: 28),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Venues near you', style: theme.textTheme.titleMedium),
                    const SizedBox(height: 2),
                    Text('Share your location to see the closest venues. Optional.', style: theme.textTheme.bodySmall),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              FilledButton(
                style: FilledButton.styleFrom(minimumSize: const Size(0, 40), padding: const EdgeInsets.symmetric(horizontal: 14)),
                onPressed: location.locating ? null : () => enableLocation(context, ref),
                child: location.locating
                    ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                    : const Text('Enable'),
              ),
            ],
          ),
        ),
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SectionHeader(title: 'Nearby venues', onSeeAll: () => context.go('/explore')),
        const SizedBox(height: 8),
        _VenueCarousel(query: nearbyQuery, emptyMessage: 'No venues within ${nearbyQuery.radiusKm?.round() ?? 25} km of you yet.'),
      ],
    );
  }
}
