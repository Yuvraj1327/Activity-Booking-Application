import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';

import 'package:zuruv/core/constants/tokens.dart';
import 'package:zuruv/customer/core/utils/format.dart';
import 'package:zuruv/customer/features/favorites/favorites_controller.dart';
import 'package:zuruv/customer/shared/models/venue.dart';
import 'package:zuruv/customer/shared/widgets/z_network_image.dart';

class SectionHeader extends StatelessWidget {
  const SectionHeader({super.key, required this.title, this.onSeeAll});

  final String title;
  final VoidCallback? onSeeAll;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: Gap.page),
      child: Row(
        children: [
          Expanded(child: Text(title, style: theme.textTheme.titleLarge)),
          if (onSeeAll != null)
            TextButton(
              onPressed: onSeeAll,
              child: const Text('See all'),
            ),
        ],
      ),
    );
  }
}

/// Illustration-free empty state: icon, headline, helper text, optional action.
class EmptyState extends StatelessWidget {
  const EmptyState({super.key, required this.icon, required this.title, this.message, this.action});

  final IconData icon;
  final String title;
  final String? message;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 72,
              height: 72,
              decoration: BoxDecoration(color: Theme.of(context).colorScheme.primaryContainer, shape: BoxShape.circle),
              child: Icon(icon, size: 34, color: theme.colorScheme.primary),
            ),
            const SizedBox(height: 16),
            Text(title, style: theme.textTheme.titleMedium, textAlign: TextAlign.center),
            if (message != null) ...[
              const SizedBox(height: 6),
              Text(message!, style: theme.textTheme.bodySmall, textAlign: TextAlign.center),
            ],
            if (action != null) ...[const SizedBox(height: 20), action!],
          ],
        ),
      ),
    );
  }
}

class RatingBadge extends StatelessWidget {
  const RatingBadge({super.key, required this.venue, this.light = false});

  final VenueSummary venue;
  final bool light;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    if (!venue.hasRating) {
      return Text('New', style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.primary, fontWeight: FontWeight.w600));
    }
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Icon(Icons.star_rounded, size: 16, color: Color(0xFFFFB400)),
        const SizedBox(width: 2),
        Text(formatRating(venue.ratingAvg!), style: theme.textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600)),
        const SizedBox(width: 4),
        Text('(${venue.ratingCount})', style: theme.textTheme.bodySmall),
      ],
    );
  }
}

class PriceLabel extends StatelessWidget {
  const PriceLabel({super.key, required this.venue, this.large = false});

  final VenueSummary venue;
  final bool large;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final price = venue.startingPricePaise;
    if (price == null) {
      return Text('Pricing soon', style: theme.textTheme.bodySmall);
    }
    return Text.rich(
      TextSpan(
        children: [
          TextSpan(
            text: formatMoney(price, currency: venue.currency),
            style: (large ? theme.textTheme.titleLarge : theme.textTheme.titleMedium)?.copyWith(color: theme.colorScheme.primary),
          ),
          TextSpan(text: '/hr', style: theme.textTheme.bodySmall),
        ],
      ),
    );
  }
}

/// Heart that toggles a favorite optimistically and reports failures.
class FavoriteButton extends ConsumerWidget {
  const FavoriteButton({super.key, required this.venue, this.size = 36, this.onLight = false, this.plain = false});

  final VenueSummary venue;
  final double size;

  /// Draw on a light background (details app bar) instead of over a photo.
  final bool onLight;

  /// No white circle behind the heart (used on list rows).
  final bool plain;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isFav = ref.watch(favoritesControllerProvider.select((m) => m[venue.id] ?? venue.isFavorite));
    return Semantics(
      button: true,
      label: isFav ? 'Remove from favorites' : 'Add to favorites',
      child: Material(
        color: plain ? Colors.transparent : Colors.white.withValues(alpha: 0.92),
        shape: const CircleBorder(),
        child: InkWell(
          customBorder: const CircleBorder(),
          onTap: () async {
            final messenger = ScaffoldMessenger.of(context);
            final ok = await ref.read(favoritesControllerProvider.notifier).toggle(venue);
            if (!ok) {
              messenger
                ..hideCurrentSnackBar()
                ..showSnackBar(const SnackBar(content: Text("Couldn't update your favorites. Please try again.")));
            }
          },
          child: SizedBox(
            width: size,
            height: size,
            child: Icon(
              isFav ? Icons.favorite_rounded : Icons.favorite_border_rounded,
              size: size * 0.55,
              color: isFav ? ZuruvColors.error : Theme.of(context).colorScheme.onSurface,
            ),
          ),
        ),
      ),
    );
  }
}

/// Star, rating, review count and the first sport, e.g. `★ 4.8 (412) · Turf · 1.9 km`.
class VenueMetaLine extends StatelessWidget {
  const VenueMetaLine({super.key, required this.venue, this.showSport = true});

  final VenueSummary venue;
  final bool showSport;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final small = theme.textTheme.bodySmall;
    final parts = <String>[
      if (showSport && venue.categories.isNotEmpty) venue.categories.first,
      if (venue.distanceKm != null) formatDistance(venue.distanceKm!),
    ];
    return Row(
      children: [
        if (venue.hasRating) ...[
          const Icon(Icons.star_rounded, size: 16, color: Color(0xFFFFB400)),
          const SizedBox(width: 3),
          Text(formatRating(venue.ratingAvg!), style: small?.copyWith(fontWeight: FontWeight.w700, color: theme.colorScheme.onSurface)),
          Text(' (${venue.ratingCount})', style: small),
        ] else
          Text('New', style: small?.copyWith(fontWeight: FontWeight.w700, color: theme.colorScheme.primary)),
        if (parts.isNotEmpty) Flexible(child: Text('  ·  ${parts.join('  ·  ')}', style: small, maxLines: 1, overflow: TextOverflow.ellipsis)),
      ],
    );
  }
}

/// `₹700/hr` in a soft blue pill.
class PricePill extends StatelessWidget {
  const PricePill({super.key, required this.venue});

  final VenueSummary venue;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final price = venue.startingPricePaise;
    if (price == null) return Text('Pricing soon', style: theme.textTheme.bodySmall);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(color: theme.colorScheme.primaryContainer, borderRadius: BorderRadius.circular(10)),
      child: Text(
        '${formatMoney(price, currency: venue.currency)}/hr',
        style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: theme.colorScheme.primary),
      ),
    );
  }
}

/// A venue counts as "Top rated" from real data only: a 4.5+ average over at least 10 reviews.
bool isTopRated(VenueSummary v) => v.hasRating && v.ratingAvg! >= 4.5 && v.ratingCount >= 10;

/// Image card used in vertical lists (explore, category).
class VenueCard extends StatelessWidget {
  const VenueCard({super.key, required this.venue, required this.onTap});

  final VenueSummary venue;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Semantics(
      button: true,
      label: venue.name,
      child: GestureDetector(
        onTap: onTap,
        behavior: HitTestBehavior.opaque,
        child: Container(
          decoration: BoxDecoration(
            color: theme.colorScheme.surface,
            borderRadius: BorderRadius.circular(Radii.card),
            border: Border.all(color: theme.colorScheme.outline),
            boxShadow: Shadows.card,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Stack(
                children: [
                  ZNetworkImage(url: venue.coverImageUrl, aspectRatio: 16 / 8.5, borderRadius: Radii.card, semanticLabel: venue.name),
                  Positioned(top: 10, right: 10, child: FavoriteButton(venue: venue)),
                  if (isTopRated(venue)) const Positioned(left: 10, bottom: 10, child: _TopRatedTag()),
                ],
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(14, 12, 14, 14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(child: Text(venue.name, style: theme.textTheme.titleMedium, maxLines: 1, overflow: TextOverflow.ellipsis)),
                        const SizedBox(width: 8),
                        PricePill(venue: venue),
                      ],
                    ),
                    const SizedBox(height: 6),
                    VenueMetaLine(venue: venue),
                    if (venue.categories.isNotEmpty) ...[
                      const SizedBox(height: 10),
                      SizedBox(
                        height: 26,
                        child: ClipRect(
                          child: Wrap(spacing: 6, children: [for (final c in venue.categories.take(3)) _SportChip(label: c)]),
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Compact horizontal card (thumbnail left) used on the Favorites screen.
class VenueRowCard extends StatelessWidget {
  const VenueRowCard({super.key, required this.venue, required this.onTap});

  final VenueSummary venue;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Semantics(
      button: true,
      label: venue.name,
      child: GestureDetector(
        onTap: onTap,
        behavior: HitTestBehavior.opaque,
        child: Container(
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            color: theme.colorScheme.surface,
            borderRadius: BorderRadius.circular(Radii.card),
            border: Border.all(color: theme.colorScheme.outline),
            boxShadow: Shadows.card,
          ),
          child: Row(
            children: [
              SizedBox(
                width: 104,
                child: ZNetworkImage(url: venue.coverImageUrl, aspectRatio: 1.1, borderRadius: 14, semanticLabel: venue.name),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(child: Text(venue.name, style: theme.textTheme.titleMedium, maxLines: 1, overflow: TextOverflow.ellipsis)),
                        FavoriteButton(venue: venue, size: 30, plain: true),
                      ],
                    ),
                    const SizedBox(height: 4),
                    VenueMetaLine(venue: venue, showSport: false),
                    const SizedBox(height: 10),
                    PricePill(venue: venue),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _TopRatedTag extends StatelessWidget {
  const _TopRatedTag();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(color: theme.colorScheme.primaryContainer, borderRadius: BorderRadius.circular(12)),
      child: Text('Top Rated', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: theme.colorScheme.primary)),
    );
  }
}

/// Narrow card for horizontal carousels on the home screen.
class VenueCarouselCard extends StatelessWidget {
  const VenueCarouselCard({super.key, required this.venue, required this.onTap, this.width = 232});

  final VenueSummary venue;
  final VoidCallback onTap;
  final double width;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SizedBox(
      width: width,
      child: GestureDetector(
        onTap: onTap,
        behavior: HitTestBehavior.opaque,
        child: Container(
          decoration: BoxDecoration(
            color: theme.colorScheme.surface,
            borderRadius: BorderRadius.circular(Radii.card),
            border: Border.all(color: theme.colorScheme.outline),
            boxShadow: Shadows.card,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Stack(
                children: [
                  ZNetworkImage(url: venue.coverImageUrl, aspectRatio: 16 / 9, borderRadius: Radii.image, semanticLabel: venue.name),
                  Positioned(top: 8, right: 8, child: FavoriteButton(venue: venue, size: 32)),
                  if (isTopRated(venue)) const Positioned(left: 8, bottom: 8, child: _TopRatedTag()),
                ],
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(child: Text(venue.name, style: theme.textTheme.titleMedium, maxLines: 1, overflow: TextOverflow.ellipsis)),
                        const SizedBox(width: 6),
                        PricePill(venue: venue),
                      ],
                    ),
                    const SizedBox(height: 6),
                    VenueMetaLine(venue: venue),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SportChip extends StatelessWidget {
  const _SportChip({required this.label});
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: Theme.of(context).colorScheme.primaryContainer, borderRadius: BorderRadius.circular(12)),
      child: Text(
        label,
        style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Theme.of(context).colorScheme.primary),
      ),
    );
  }
}

class VenueCardSkeleton extends StatelessWidget {
  const VenueCardSkeleton({super.key});

  @override
  Widget build(BuildContext context) {
    return const Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        AspectRatio(aspectRatio: 16 / 9, child: ShimmerBox(radius: Radii.card)),
        SizedBox(height: 12),
        ShimmerBox(height: 16, width: 180, radius: 6),
        SizedBox(height: 8),
        ShimmerBox(height: 12, width: 120, radius: 6),
      ],
    );
  }
}

/// Inline row shown under a list while the next page loads or failed.
class ListFooter extends StatelessWidget {
  const ListFooter({super.key, required this.loading, required this.error, required this.onRetry});

  final bool loading;
  final bool error;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    if (loading) {
      return const Padding(padding: EdgeInsets.all(20), child: Center(child: CircularProgressIndicator(strokeWidth: 2.5)));
    }
    if (error) {
      return Padding(
        padding: const EdgeInsets.all(12),
        child: Center(
          child: TextButton.icon(onPressed: onRetry, icon: const Icon(Icons.refresh_rounded), label: const Text("Couldn't load more. Retry")),
        ),
      );
    }
    return const SizedBox(height: 16);
  }
}
