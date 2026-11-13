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
              decoration: const BoxDecoration(color: ZuruvColors.primaryTint, shape: BoxShape.circle),
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
  const FavoriteButton({super.key, required this.venue, this.size = 36, this.onLight = false});

  final VenueSummary venue;
  final double size;

  /// Draw on a light background (details app bar) instead of over a photo.
  final bool onLight;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isFav = ref.watch(favoritesControllerProvider.select((m) => m[venue.id] ?? venue.isFavorite));
    return Semantics(
      button: true,
      label: isFav ? 'Remove from favorites' : 'Add to favorites',
      child: Material(
        color: Colors.white.withValues(alpha: 0.92),
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
              color: isFav ? ZuruvColors.error : ZuruvColors.text,
            ),
          ),
        ),
      ),
    );
  }
}

/// Image card used in vertical lists (explore, category, favorites).
class VenueCard extends StatelessWidget {
  const VenueCard({super.key, required this.venue, required this.onTap});

  final VenueSummary venue;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final where = joinLocation(venue.addressLine, venue.cityName);
    return Semantics(
      button: true,
      label: venue.name,
      child: GestureDetector(
        onTap: onTap,
        behavior: HitTestBehavior.opaque,
        child: Container(
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(Radii.card),
            border: Border.all(color: ZuruvColors.border),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Stack(
                children: [
                  ZNetworkImage(
                    url: venue.coverImageUrl,
                    aspectRatio: 16 / 9,
                    borderRadius: Radii.card,
                    semanticLabel: venue.name,
                  ),
                  Positioned(top: 10, right: 10, child: FavoriteButton(venue: venue)),
                  if (venue.distanceKm != null)
                    Positioned(
                      left: 10,
                      bottom: 10,
                      child: _Pill(label: formatDistance(venue.distanceKm!), icon: Icons.near_me_rounded),
                    ),
                ],
              ),
              Padding(
                padding: const EdgeInsets.all(Gap.md + 2),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                          child: Text(venue.name, style: theme.textTheme.titleMedium, maxLines: 1, overflow: TextOverflow.ellipsis),
                        ),
                        const SizedBox(width: 8),
                        RatingBadge(venue: venue),
                      ],
                    ),
                    if (where.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          const Icon(Icons.place_outlined, size: 15, color: ZuruvColors.textSecondary),
                          const SizedBox(width: 4),
                          Expanded(child: Text(where, style: theme.textTheme.bodySmall, maxLines: 1, overflow: TextOverflow.ellipsis)),
                        ],
                      ),
                    ],
                    const SizedBox(height: 8),
                    PriceLabel(venue: venue),
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
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Stack(
              children: [
                ZNetworkImage(url: venue.coverImageUrl, aspectRatio: 4 / 3, borderRadius: Radii.image, semanticLabel: venue.name),
                Positioned(top: 8, right: 8, child: FavoriteButton(venue: venue, size: 32)),
                if (venue.distanceKm != null)
                  Positioned(left: 8, bottom: 8, child: _Pill(label: formatDistance(venue.distanceKm!), icon: Icons.near_me_rounded)),
              ],
            ),
            const SizedBox(height: 10),
            Text(venue.name, style: theme.textTheme.titleMedium, maxLines: 1, overflow: TextOverflow.ellipsis),
            const SizedBox(height: 2),
            Text(
              joinLocation(null, venue.cityName ?? venue.addressLine),
              style: theme.textTheme.bodySmall,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 6),
            Row(
              children: [
                PriceLabel(venue: venue),
                const Spacer(),
                RatingBadge(venue: venue),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _Pill extends StatelessWidget {
  const _Pill({required this.label, required this.icon});
  final String label;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(color: Colors.black.withValues(alpha: 0.6), borderRadius: BorderRadius.circular(12)),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: Colors.white),
          const SizedBox(width: 4),
          Text(label, style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }
}

class VenueCardSkeleton extends StatelessWidget {
  const VenueCardSkeleton({super.key});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: const [
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
