import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:go_router/go_router.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';

import 'package:zuruv/customer/features/notifications/notifications_screen.dart';
import 'package:zuruv/core/constants/tokens.dart';
import 'package:zuruv/core/maps/maps_config.dart';
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
import 'package:zuruv/customer/features/map/venues_map_screen.dart';
import 'package:zuruv/customer/features/home/home_providers.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final auth = ref.watch(authControllerProvider);
    final firstName =
        auth is Authenticated ? auth.profile.fullName.split(' ').first : '';
    final city = ref.watch(locationControllerProvider.select((s) => s.city));
    final popularQuery = ref.watch(homePopularQueryProvider);

    Future<void> refresh() async {
      ref.invalidate(categoriesProvider);
      await ref
          .read(venueListControllerProvider(popularQuery).notifier)
          .refresh();
      final nearby = ref.read(homeNearbyQueryProvider);
      if (nearby != null) {
        await ref.read(venueListControllerProvider(nearby).notifier).refresh();
      }
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
                padding:
                    const EdgeInsets.fromLTRB(Gap.page, 12, Gap.page - 6, 0),
                child: Row(
                  children: [
                    Expanded(
                      child: Align(
                        alignment: Alignment.centerLeft,
                        child: InkWell(
                          borderRadius: BorderRadius.circular(12),
                          onTap: () => showCitySheet(context),
                          child: Padding(
                            padding: const EdgeInsets.symmetric(
                                vertical: 6, horizontal: 2),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(Icons.place_rounded,
                                    size: 20, color: theme.colorScheme.primary),
                                const SizedBox(width: 6),
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
                          ),
                        ),
                      ),
                    ),
                    IconButton(
                      tooltip: 'Notifications',
                      onPressed: () => context.push('/notifications'),
                      icon: Badge(
                        smallSize: 9,
                        isLabelVisible:
                            (ref.watch(unreadCountProvider).valueOrNull ?? 0) >
                                0,
                        child: const Icon(Icons.notifications_none_rounded,
                            size: 28),
                      ),
                    ),
                  ],
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(Gap.page, 8, Gap.page, 0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                        firstName.isEmpty ? 'Hi Player 👋' : 'Hi $firstName 👋',
                        style: theme.textTheme.headlineMedium),
                    const SizedBox(height: 4),
                    Text('Find and book sports venues near you.',
                        style: theme.textTheme.bodyMedium
                            ?.copyWith(color: ZuruvColors.textSecondary)),
                  ],
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
              const SizedBox(height: 18),
              _PromoBanner(onTap: () => context.go('/explore')),
              const SizedBox(height: 18),
              const _CategoryRow(),
              const SizedBox(height: 20),
              _MapPreview(query: popularQuery),
              const SizedBox(height: 24),
              SectionHeader(
                  title: 'Popular venues',
                  onSeeAll: () => context.go('/explore')),
              const SizedBox(height: 8),
              _VenueCarousel(
                  query: popularQuery,
                  emptyMessage: city == null
                      ? 'No venues are listed yet.'
                      : 'No venues in ${city.name} yet.'),
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
            color: Theme.of(context).colorScheme.primaryContainer,
            borderRadius: BorderRadius.circular(26),
          ),
          child: Row(
            children: [
              Icon(Icons.search_rounded,
                  color: Theme.of(context).colorScheme.primary),
              const SizedBox(width: 10),
              Expanded(
                child: Text('Search venues, sports or areas',
                    style: Theme.of(context)
                        .textTheme
                        .bodyMedium
                        ?.copyWith(color: ZuruvColors.textSecondary),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis),
              ),
              Icon(Icons.tune_rounded,
                  color: Theme.of(context).colorScheme.primary),
            ],
          ),
        ),
      ),
    );
  }
}

class _PromoBanner extends StatelessWidget {
  const _PromoBanner({required this.onTap});
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: Gap.page),
      child: Semantics(
        button: true,
        label: 'Book sports venues',
        child: GestureDetector(
          onTap: onTap,
          child: ClipRRect(
            borderRadius: BorderRadius.circular(Radii.sheet - 4),
            child: AspectRatio(
              aspectRatio: 1677 / 737,
              child: Image.asset('assets/images/home_banner.png',
                  fit: BoxFit.cover),
            ),
          ),
        ),
      ),
    );
  }
}

class _CategoryRow extends ConsumerWidget {
  const _CategoryRow();

  static const int _maxShown = 5; // + "More"

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final categories = ref.watch(categoriesProvider);
    return categories.when(
      loading: () => const _CategorySkeleton(),
      error: (e, _) => Padding(
        padding: const EdgeInsets.symmetric(horizontal: Gap.page),
        child: Row(
          children: [
            Expanded(
                child: Text(errorMessage(e),
                    style: Theme.of(context).textTheme.bodySmall)),
            TextButton(
                onPressed: () => ref.invalidate(categoriesProvider),
                child: const Text('Retry')),
          ],
        ),
      ),
      data: (list) {
        if (list.isEmpty) return const SizedBox.shrink();
        final shown = list.take(_maxShown).toList();
        final hasMore = list.length > shown.length;
        final tiles = <Widget>[
          for (final c in shown)
            _CategoryTile(
              icon: SportIcon(iconKey: c.iconKey, slug: c.slug, size: 34),
              label: c.name,
              onTap: () => context.push('/category/${c.slug}'),
            ),
          if (hasMore)
            _CategoryTile(
              icon: Icon(Icons.apps_rounded,
                  size: 30, color: Theme.of(context).colorScheme.primary),
              label: 'More',
              onTap: () => _showAllCategories(context, list),
            ),
        ];
        return SizedBox(
          height: 92,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: Gap.page),
            itemCount: tiles.length,
            separatorBuilder: (_, __) => const SizedBox(width: 10),
            itemBuilder: (_, i) => SizedBox(width: 68, child: tiles[i]),
          ),
        );
      },
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
            Text('All sports',
                style: Theme.of(sheetContext).textTheme.titleLarge),
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
                      icon:
                          SportIcon(iconKey: c.iconKey, slug: c.slug, size: 34),
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

/// Small map card: venue pins around the user, with a button to open the full map.
class _MapPreview extends ConsumerWidget {
  const _MapPreview({required this.query});
  final VenueQuery query;

  static const _fallbackCenter = LatLng(12.9716, 77.5946); // Bangalore

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final available = ref.watch(mapsAvailableProvider);
    final location = ref.watch(locationControllerProvider);
    final venues = ref
        .watch(venueListControllerProvider(query))
        .items
        .where((v) => v.latitude != null && v.longitude != null)
        .toList();
    final center = location.point != null
        ? LatLng(location.point!.lat, location.point!.lng)
        : venues.isNotEmpty
            ? LatLng(venues.first.latitude!, venues.first.longitude!)
            : _fallbackCenter;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: Gap.page),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(Radii.card),
        child: SizedBox(
          height: 150,
          child: Stack(
            children: [
              Positioned.fill(
                child: available
                    ? IgnorePointer(
                        child: GoogleMap(
                          key: ValueKey(
                              '${center.latitude},${center.longitude},${venues.length}'),
                          initialCameraPosition:
                              CameraPosition(target: center, zoom: 11.5),
                          markers: {
                            for (final v in venues)
                              Marker(
                                  markerId: MarkerId(v.id),
                                  position: LatLng(v.latitude!, v.longitude!)),
                          },
                          myLocationEnabled: false,
                          myLocationButtonEnabled: false,
                          zoomControlsEnabled: false,
                          mapToolbarEnabled: false,
                          compassEnabled: false,
                        ),
                      )
                    : Container(
                        color: Theme.of(context).colorScheme.primaryContainer,
                        child: Center(
                            child: Icon(Icons.map_outlined,
                                size: 44,
                                color: theme.colorScheme.primary
                                    .withValues(alpha: 0.4))),
                      ),
              ),
              if (location.city != null)
                Positioned(
                  left: 16,
                  top: 0,
                  bottom: 0,
                  child: Center(
                    child: Row(children: [
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                            color: theme.colorScheme.surface,
                            shape: BoxShape.circle,
                            boxShadow: Shadows.card),
                        child: Icon(Icons.place_rounded,
                            size: 18, color: theme.colorScheme.primary),
                      ),
                      const SizedBox(width: 8),
                      Text(location.city!.name,
                          style: theme.textTheme.titleLarge
                              ?.copyWith(fontWeight: FontWeight.w800)),
                    ]),
                  ),
                ),
              Positioned(
                right: 12,
                bottom: 12,
                child: Material(
                  color: Theme.of(context).colorScheme.surface,
                  elevation: 2,
                  borderRadius: BorderRadius.circular(22),
                  child: InkWell(
                    borderRadius: BorderRadius.circular(22),
                    onTap: () => Navigator.of(context).push(
                        MaterialPageRoute<void>(
                            builder: (_) => VenuesMapScreen(query: query))),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 16, vertical: 10),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text('View on Map',
                              style: theme.textTheme.titleSmall?.copyWith(
                                  color: theme.colorScheme.primary,
                                  fontWeight: FontWeight.w700)),
                          const SizedBox(width: 4),
                          Icon(Icons.north_east_rounded,
                              size: 16, color: theme.colorScheme.primary),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _CategoryTile extends StatelessWidget {
  const _CategoryTile(
      {required this.icon, required this.label, required this.onTap});
  final Widget icon;
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
              decoration: BoxDecoration(
                color: theme.colorScheme.surface,
                borderRadius: BorderRadius.circular(18),
                border: Border.all(color: theme.colorScheme.outline),
                boxShadow: Shadows.card,
              ),
              alignment: Alignment.center,
              child: icon,
            ),
            const SizedBox(height: 8),
            Text(label,
                style: theme.textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurface,
                    fontWeight: FontWeight.w500),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                textAlign: TextAlign.center),
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
    return SizedBox(
      height: 92,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        physics: const NeverScrollableScrollPhysics(),
        padding: const EdgeInsets.symmetric(horizontal: Gap.page),
        itemCount: 6,
        separatorBuilder: (_, __) => const SizedBox(width: 10),
        itemBuilder: (_, __) => const SizedBox(
          width: 68,
          child: Column(children: [
            ShimmerBox(height: 60, width: 60, radius: 20),
            SizedBox(height: 8),
            ShimmerBox(height: 10, width: 44, radius: 5)
          ]),
        ),
      ),
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
          itemBuilder: (_, __) =>
              const SizedBox(width: 232, child: VenueCardSkeleton()),
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
      height: 278,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: Gap.page),
        itemCount: state.items.length,
        separatorBuilder: (_, __) => const SizedBox(width: 14),
        itemBuilder: (context, i) {
          final venue = state.items[i];
          return VenueCarouselCard(
              venue: venue, onTap: () => context.push('/venues/${venue.id}'));
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
          decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.primaryContainer,
              borderRadius: BorderRadius.circular(Radii.card)),
          child: Row(
            children: [
              Icon(Icons.near_me_rounded,
                  color: theme.colorScheme.primary, size: 28),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Venues near you', style: theme.textTheme.titleMedium),
                    const SizedBox(height: 2),
                    Text(
                        'Share your location to see the closest venues. Optional.',
                        style: theme.textTheme.bodySmall),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              FilledButton(
                style: FilledButton.styleFrom(
                    minimumSize: const Size(0, 40),
                    padding: const EdgeInsets.symmetric(horizontal: 14)),
                onPressed: location.locating
                    ? null
                    : () => enableLocation(context, ref),
                child: location.locating
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                            strokeWidth: 2, color: Colors.white))
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
        SectionHeader(
            title: 'Nearby venues', onSeeAll: () => context.go('/explore')),
        const SizedBox(height: 8),
        const _DistanceChips(),
        const SizedBox(height: 14),
        _VenueCarousel(
            query: nearbyQuery,
            emptyMessage:
                'No venues within ${nearbyQuery.radiusKm?.round() ?? 5} km of you yet.'),
      ],
    );
  }
}

class _DistanceChips extends ConsumerWidget {
  const _DistanceChips();

  static const _options = <(String, double)>[
    ('Within 5 km', 5),
    ('5 – 10 km', 10),
    ('10 – 25 km', 25)
  ];

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final selected = ref.watch(homeNearbyRadiusProvider);
    return SizedBox(
      height: 40,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: Gap.page),
        children: [
          for (final (label, km) in _options)
            Padding(
              padding: const EdgeInsets.only(right: 10),
              child: ChoiceChip(
                label: Text(label),
                selected: selected == km,
                showCheckmark: false,
                selectedColor: theme.colorScheme.primary,
                backgroundColor: Theme.of(context).colorScheme.primaryContainer,
                side: BorderSide.none,
                labelStyle: TextStyle(
                    fontWeight: FontWeight.w600,
                    color: selected == km
                        ? Colors.white
                        : ZuruvColors.textSecondary),
                onSelected: (_) =>
                    ref.read(homeNearbyRadiusProvider.notifier).state = km,
              ),
            ),
          TextButton.icon(
            onPressed: () => _setDistance(context, ref, selected),
            icon: const Icon(Icons.place_outlined, size: 18),
            label: const Text('Set distance'),
          ),
        ],
      ),
    );
  }

  Future<void> _setDistance(
      BuildContext context, WidgetRef ref, double current) async {
    var value = current.clamp(1, 50).toDouble();
    final result = await showModalBottomSheet<double>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setState) => Padding(
          padding: const EdgeInsets.fromLTRB(Gap.page, 0, Gap.page, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Within ${value.round()} km',
                  style: Theme.of(ctx).textTheme.titleLarge),
              Slider(
                  value: value,
                  min: 1,
                  max: 50,
                  divisions: 49,
                  label: '${value.round()} km',
                  onChanged: (v) => setState(() => value = v)),
              SizedBox(
                  width: double.infinity,
                  child: FilledButton(
                      onPressed: () =>
                          Navigator.of(ctx).pop(value.roundToDouble()),
                      child: const Text('Apply'))),
            ],
          ),
        ),
      ),
    );
    if (result != null) {
      ref.read(homeNearbyRadiusProvider.notifier).state = result;
    }
  }
}
