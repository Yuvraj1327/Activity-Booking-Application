import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:go_router/go_router.dart';

import 'package:zuruv/core/constants/tokens.dart';
import 'package:zuruv/core/network/api_helpers.dart';
import 'package:zuruv/customer/core/utils/format.dart';
import 'package:zuruv/customer/shared/models/venue.dart';
import 'package:zuruv/customer/shared/widgets/category_icons.dart';
import 'package:zuruv/customer/shared/widgets/common_widgets.dart';
import 'package:zuruv/customer/shared/widgets/z_network_image.dart';
import 'package:zuruv/customer/features/reviews/review_widgets.dart';
import 'package:zuruv/customer/features/venue_details/directions_launcher.dart';
import 'package:zuruv/customer/features/venue_details/venue_detail_provider.dart';

class VenueDetailsScreen extends ConsumerWidget {
  const VenueDetailsScreen({super.key, required this.venueId});

  final String venueId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final detail = ref.watch(venueDetailProvider(venueId));
    return detail.when(
      loading: () => const _Frame(child: LoadingView()),
      error: (e, _) {
        final notFound = e is ApiException && e.statusCode == 404;
        return _Frame(
          child: notFound
              ? EmptyState(
                  icon: Icons.location_off_outlined,
                  title: 'This venue is no longer available',
                  action: OutlinedButton(onPressed: () => context.pop(), child: const Text('Go back')),
                )
              : ErrorView(message: errorMessage(e), onRetry: () => ref.invalidate(venueDetailProvider(venueId))),
        );
      },
      data: (venue) => _Content(venue: venue),
    );
  }
}

/// Scaffold with a back button, for the loading / error states.
class _Frame extends StatelessWidget {
  const _Frame({required this.child});
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(leading: IconButton(onPressed: () => context.pop(), icon: const Icon(Icons.arrow_back_rounded))),
      body: child,
    );
  }
}

class _Content extends ConsumerWidget {
  const _Content({required this.venue});
  final VenueDetail venue;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final where = joinLocation(venue.addressLine, venue.cityName);
    final fullAddress = [if (where.isNotEmpty) where, if (venue.postalCode != null) venue.postalCode!].join(' ');
    return Scaffold(
      bottomNavigationBar: _BookBar(venue: venue),
      body: CustomScrollView(
        slivers: [
          SliverAppBar(
            pinned: true,
            expandedHeight: 300,
            backgroundColor: Colors.white,
            automaticallyImplyLeading: false,
            leading: Padding(
              padding: const EdgeInsets.all(6),
              child: Material(
                color: Colors.white.withValues(alpha: 0.92),
                shape: const CircleBorder(),
                child: IconButton(
                  tooltip: 'Back',
                  onPressed: () => context.pop(),
                  icon: const Icon(Icons.arrow_back_rounded, color: ZuruvColors.text),
                ),
              ),
            ),
            actions: [Padding(padding: const EdgeInsets.all(8), child: FavoriteButton(venue: venue, size: 40))],
            flexibleSpace: FlexibleSpaceBar(background: _Gallery(urls: venue.galleryUrls, name: venue.name)),
          ),
          SliverToBoxAdapter(
            child: Align(
              alignment: Alignment.topCenter,
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 720),
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(Gap.page, 16, Gap.page, 24),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(venue.name, style: theme.textTheme.headlineMedium),
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          RatingBadge(venue: venue),
                          const SizedBox(width: 8),
                          Text(
                            venue.hasRating ? '· ${venue.ratingCount} ${venue.ratingCount == 1 ? 'review' : 'reviews'}' : '· No reviews yet',
                            style: theme.textTheme.bodySmall,
                          ),
                        ],
                      ),
                      if (venue.categoryDetails.isNotEmpty) ...[
                        const SizedBox(height: 14),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: [
                            for (final c in venue.categoryDetails)
                              Chip(
                                avatar: Icon(categoryIcon(c.iconKey, slug: c.slug), size: 16, color: theme.colorScheme.primary),
                                label: Text(c.name),
                                backgroundColor: ZuruvColors.primaryTint,
                                side: BorderSide.none,
                              ),
                          ],
                        ),
                      ],
                      const SizedBox(height: 20),
                      _InfoRow(
                        icon: Icons.place_outlined,
                        title: fullAddress.isEmpty ? 'Address not provided' : fullAddress,
                        subtitle: venue.distanceKm == null ? null : '${formatDistance(venue.distanceKm!)} from you',
                      ),
                      if (venue.latitude != null && venue.longitude != null)
                        Align(
                          alignment: Alignment.centerLeft,
                          child: TextButton.icon(
                            onPressed: () async {
                              final messenger = ScaffoldMessenger.of(context);
                              final ok = await ref
                                  .read(directionsLauncherProvider)
                                  .open(latitude: venue.latitude!, longitude: venue.longitude!);
                              if (!ok) {
                                messenger.showSnackBar(const SnackBar(content: Text('Could not open maps on this device.')));
                              }
                            },
                            icon: const Icon(Icons.directions_outlined),
                            label: const Text('Directions'),
                          ),
                        ),
                      if (venue.contactPhone != null) ...[
                        const SizedBox(height: 12),
                        _InfoRow(icon: Icons.call_outlined, title: venue.contactPhone!),
                      ],
                      const SizedBox(height: 12),
                      _InfoRow(
                        icon: Icons.payments_outlined,
                        title: venue.startingPricePaise == null
                            ? 'Pricing will be shown soon'
                            : 'From ${formatMoney(venue.startingPricePaise!, currency: venue.currency)} per hour',
                        subtitle: venue.startingPricePaise == null ? null : 'Final price depends on the slot you choose',
                      ),
                      if (venue.description != null && venue.description!.trim().isNotEmpty) ...[
                        const SizedBox(height: 24),
                        Text('About', style: theme.textTheme.titleLarge),
                        const SizedBox(height: 8),
                        _ExpandableText(text: venue.description!.trim()),
                      ],
                      if (venue.amenities.isNotEmpty) ...[
                        const SizedBox(height: 24),
                        Text('Facilities & amenities', style: theme.textTheme.titleLarge),
                        const SizedBox(height: 12),
                        Wrap(
                          spacing: 10,
                          runSpacing: 10,
                          children: [
                            for (final a in venue.amenities)
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                                decoration: BoxDecoration(
                                  border: Border.all(color: ZuruvColors.border),
                                  borderRadius: BorderRadius.circular(Radii.button),
                                ),
                                child: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    Icon(amenityIcon(a.iconKey, slug: a.slug), size: 18, color: theme.colorScheme.primary),
                                    const SizedBox(width: 8),
                                    Text(a.name, style: theme.textTheme.bodyMedium),
                                  ],
                                ),
                              ),
                          ],
                        ),
                      ],
                      const SizedBox(height: 24),
                      VenueReviewsSection(venueId: venue.id),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({required this.icon, required this.title, this.subtitle});
  final IconData icon;
  final String title;
  final String? subtitle;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 22, color: theme.colorScheme.primary),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: theme.textTheme.bodyLarge),
              if (subtitle != null) Text(subtitle!, style: theme.textTheme.bodySmall),
            ],
          ),
        ),
      ],
    );
  }
}

class _ExpandableText extends StatefulWidget {
  const _ExpandableText({required this.text});
  final String text;

  @override
  State<_ExpandableText> createState() => _ExpandableTextState();
}

class _ExpandableTextState extends State<_ExpandableText> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return LayoutBuilder(
      builder: (context, constraints) {
        final painter = TextPainter(
          text: TextSpan(text: widget.text, style: theme.textTheme.bodyLarge),
          maxLines: 4,
          textDirection: Directionality.of(context),
          textScaler: MediaQuery.textScalerOf(context),
        )..layout(maxWidth: constraints.maxWidth);
        final overflows = painter.didExceedMaxLines;
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(widget.text, style: theme.textTheme.bodyLarge, maxLines: _expanded ? null : 4, overflow: _expanded ? TextOverflow.visible : TextOverflow.ellipsis),
            if (overflows)
              GestureDetector(
                onTap: () => setState(() => _expanded = !_expanded),
                child: Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Text(_expanded ? 'Show less' : 'Read more', style: TextStyle(color: theme.colorScheme.primary, fontWeight: FontWeight.w600)),
                ),
              ),
          ],
        );
      },
    );
  }
}

class _Gallery extends StatefulWidget {
  const _Gallery({required this.urls, required this.name});
  final List<String> urls;
  final String name;

  @override
  State<_Gallery> createState() => _GalleryState();
}

class _GalleryState extends State<_Gallery> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    if (widget.urls.isEmpty) {
      return const SizedBox.expand(child: ImageFallback());
    }
    return Stack(
      fit: StackFit.expand,
      children: [
        PageView.builder(
          itemCount: widget.urls.length,
          onPageChanged: (i) => setState(() => _index = i),
          itemBuilder: (_, i) => ZNetworkImage(url: widget.urls[i], borderRadius: 0, semanticLabel: '${widget.name}, photo ${i + 1}'),
        ),
        if (widget.urls.length > 1)
          Positioned(
            bottom: 12,
            left: 0,
            right: 0,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                for (var i = 0; i < widget.urls.length; i++)
                  AnimatedContainer(
                    duration: const Duration(milliseconds: 180),
                    margin: const EdgeInsets.symmetric(horizontal: 3),
                    width: i == _index ? 18 : 7,
                    height: 7,
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: i == _index ? 1 : 0.6),
                      borderRadius: BorderRadius.circular(4),
                    ),
                  ),
              ],
            ),
          ),
      ],
    );
  }
}

class _BookBar extends StatelessWidget {
  const _BookBar({required this.venue});
  final VenueDetail venue;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SafeArea(
      child: Container(
        padding: const EdgeInsets.fromLTRB(Gap.page, 12, Gap.page, 12),
        decoration: const BoxDecoration(color: Colors.white, border: Border(top: BorderSide(color: ZuruvColors.border))),
        child: Row(
          children: [
            Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Starting from', style: theme.textTheme.bodySmall),
                PriceLabel(venue: venue, large: true),
              ],
            ),
            const SizedBox(width: 20),
            Expanded(
              child: FilledButton(
                onPressed: () => context.push('/venues/${venue.id}/book'),
                child: const Text('Book Now'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
