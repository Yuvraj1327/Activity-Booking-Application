import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:go_router/go_router.dart';

import 'package:zuruv/core/constants/tokens.dart';
import 'package:zuruv/core/theme/owner_theme.dart';
import 'package:zuruv/owner/core/utils/format.dart';
import 'package:zuruv/owner/shared/models/models.dart';
import 'package:zuruv/owner/shared/repositories/owner_repository.dart';
import 'package:zuruv/owner/shared/widgets/common_widgets.dart';
import 'package:zuruv/owner/shared/widgets/z_network_image.dart';
import 'package:zuruv/owner/features/notifications/notifications_screen.dart';

/// Real data from `GET /owners/dashboard`. Booking and revenue figures come back as
/// "unavailable" until Steps 6 and 7 exist, and are shown that way, never as zeros or samples.
final dashboardProvider =
    FutureProvider.autoDispose<Dashboard>((ref) => ref.watch(ownerRepositoryProvider).dashboard());

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final dash = ref.watch(dashboardProvider);
    final auth = ref.watch(authControllerProvider);
    final name = auth is Authenticated ? auth.profile.fullName.split(' ').first : '';
    final unread = ref.watch(unreadCountProvider);

    return Scaffold(
      appBar: AppBar(
        toolbarHeight: 72,
        titleSpacing: Gap.page,
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(name.isEmpty ? 'Dashboard' : 'Hello, $name 👋', maxLines: 1, overflow: TextOverflow.ellipsis),
            const SizedBox(height: 2),
            Text(
              "Here's your venue performance",
              style: Theme.of(context).textTheme.bodySmall?.copyWith(color: ZuruvColors.textSecondary, fontWeight: FontWeight.w500),
            ),
          ],
        ),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: Gap.md),
            child: IconButton.filledTonal(
              tooltip: 'Notifications',
              onPressed: () => context.push('/owner/notifications'),
              icon: Badge(
                isLabelVisible: unread > 0,
                label: Text(unread > 9 ? '9+' : '$unread'),
                child: const Icon(Icons.notifications_none_rounded),
              ),
            ),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(dashboardProvider);
          ref.invalidate(notificationsProvider);
          try {
            await ref.read(dashboardProvider.future);
          } catch (_) {
            // The error view shows the failure.
          }
        },
        child: dash.when(
          loading: () => const _DashboardSkeleton(),
          error: (e, _) => ListView(children: [
            SizedBox(height: 420, child: ErrorView.fromError(e, onRetry: () => ref.invalidate(dashboardProvider))),
          ]),
          data: (d) => _Content(d: d),
        ),
      ),
    );
  }
}

class _Content extends StatelessWidget {
  const _Content({required this.d});
  final Dashboard d;

  @override
  Widget build(BuildContext context) {
    if (d.venuesTotal == 0) {
      return ListView(children: [
        SizedBox(
          height: 460,
          child: EmptyState(
            icon: Icons.add_business_rounded,
            title: 'Add your first venue',
            message: 'Create a listing with photos and pricing, then publish it so players can find you.',
            actionLabel: 'Add venue',
            onAction: () => context.push('/owner/venues/new'),
          ),
        ),
      ]);
    }
    final unpublished = d.venuesTotal - d.venuesPublished;
    return ResponsivePage(
      maxWidth: 720,
      child: ListView(
        padding: const EdgeInsets.only(bottom: 32, top: 4),
        children: [
          const HeroStatCard(label: 'Total revenue', icon: Icons.bar_chart_rounded, note: 'Available with payments'),
          const SizedBox(height: Gap.md),
          _TileRow(
            left: StatTile(label: 'Total bookings', icon: Icons.event_available_rounded, value: '${d.totalBookings}'),
            right: const StatTile(label: 'Avg. utilization', icon: Icons.pie_chart_outline_rounded, note: 'Available with online booking'),
          ),
          const SizedBox(height: Gap.md),
          _TileRow(
            left: StatTile(
              label: 'Avg. rating',
              icon: Icons.star_rounded,
              value: d.averageRating == null ? null : formatRating(d.averageRating!),
              note: d.averageRating == null ? 'No ratings yet' : '${d.ratingsCount} ratings',
            ),
            right: StatTile(
              label: 'Your venues',
              icon: Icons.layers_rounded,
              value: '${d.venuesTotal}',
              note: '${d.venuesPublished} published${unpublished > 0 ? ' · ${d.venuesDraft} draft' : ''}',
            ),
          ),
          const SectionHeader('Monthly revenue'),
          UnavailableCard(title: 'Not available yet', message: d.monthlyRevenue.message, icon: Icons.show_chart_rounded),
          const SectionHeader('Booking overview'),
          IntrinsicHeight(
            child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              Expanded(child: _OverviewTile(label: 'Upcoming', value: d.bookingOverview.upcoming, icon: Icons.event_outlined, color: OwnerColors.blue)),
              const SizedBox(width: Gap.md),
              Expanded(child: _OverviewTile(label: 'Completed', value: d.bookingOverview.completed, icon: Icons.check_circle_outline_rounded, color: ZuruvColors.success)),
              const SizedBox(width: Gap.md),
              Expanded(child: _OverviewTile(label: 'Cancelled', value: d.bookingOverview.cancelled, icon: Icons.cancel_outlined, color: ZuruvColors.error)),
            ]),
          ),
          SectionHeader('Venue performance', action: 'Analytics', onAction: () => context.push('/owner/analytics')),
          for (final v in d.performance) _PerformanceRow(v: v),
          SectionHeader('Recent activity', action: 'See all', onAction: () => context.push('/owner/notifications')),
          if (d.recent.isEmpty)
            const UnavailableCard(
              title: 'Nothing yet',
              message: 'New bookings, payments and reviews will show up here.',
              icon: Icons.notifications_none_rounded,
            )
          else
            for (final n in d.recent.take(5)) _ActivityRow(n: n),
        ],
      ),
    );
  }
}

class _TileRow extends StatelessWidget {
  const _TileRow({required this.left, required this.right});
  final Widget left;
  final Widget right;

  @override
  Widget build(BuildContext context) => IntrinsicHeight(
        child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Expanded(child: left),
          const SizedBox(width: Gap.md),
          Expanded(child: right),
        ]),
      );
}

class _OverviewTile extends StatelessWidget {
  const _OverviewTile({required this.label, required this.value, required this.icon, required this.color});
  final String label;
  final int value;
  final IconData icon;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return OwnerCard(
      padding: const EdgeInsets.symmetric(vertical: Gap.lg, horizontal: Gap.sm),
      child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
        Icon(icon, color: color, size: 26),
        const SizedBox(height: 8),
        Text(label, style: theme.textTheme.bodySmall?.copyWith(color: ZuruvColors.textSecondary, fontWeight: FontWeight.w600), maxLines: 1, overflow: TextOverflow.ellipsis),
        const SizedBox(height: 2),
        Text('$value', style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
      ]),
    );
  }
}

class _PerformanceRow extends StatelessWidget {
  const _PerformanceRow({required this.v});
  final PerformanceVenue v;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: Gap.md),
      child: OwnerCard(
        padding: const EdgeInsets.all(Gap.md),
        onTap: () => context.push('/owner/venues/${v.venueId}'),
        child: Row(children: [
          SizedBox(width: 56, height: 56, child: ZNetworkImage(url: v.coverImageUrl, borderRadius: 14)),
          const SizedBox(width: Gap.md),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(v.name, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
              const SizedBox(height: 4),
              RatingText(rating: v.ratingAvg, count: v.ratingCount),
            ]),
          ),
          const SizedBox(width: Gap.sm),
          Flexible(flex: 2, child: StatusChip(v.status)),
        ]),
      ),
    );
  }
}

class _ActivityRow extends StatelessWidget {
  const _ActivityRow({required this.n});
  final OwnerNotification n;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: IconBadge(iconForNotification(n.type), size: 40),
      title: Text(n.title, maxLines: 1, overflow: TextOverflow.ellipsis),
      subtitle: Text(timeAgo(n.createdAt)),
    );
  }
}

class _DashboardSkeleton extends StatelessWidget {
  const _DashboardSkeleton();

  @override
  Widget build(BuildContext context) {
    return ListView(
      physics: const NeverScrollableScrollPhysics(),
      padding: const EdgeInsets.all(Gap.page),
      children: [
        const ShimmerBox(height: 110, radius: 22),
        const SizedBox(height: Gap.md),
        const Row(children: [
          Expanded(child: ShimmerBox(height: 104, radius: Radii.card)),
          SizedBox(width: Gap.md),
          Expanded(child: ShimmerBox(height: 104, radius: Radii.card)),
        ]),
        const SizedBox(height: Gap.xl),
        const ShimmerBox(height: 72, radius: Radii.card),
        const SizedBox(height: Gap.md),
        const ShimmerBox(height: 72, radius: Radii.card),
      ],
    );
  }
}
