import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:go_router/go_router.dart';

import 'package:zuruv/core/constants/tokens.dart';
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
        title: Text(name.isEmpty ? 'Dashboard' : 'Hello, $name'),
        actions: [
          IconButton(
            tooltip: 'Notifications',
            onPressed: () => context.push('/owner/notifications'),
            icon: Badge(
              isLabelVisible: unread > 0,
              label: Text(unread > 9 ? '9+' : '$unread'),
              child: const Icon(Icons.notifications_none_rounded),
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
    return ResponsivePage(
      maxWidth: 720,
      child: ListView(
        padding: const EdgeInsets.only(bottom: 32, top: 8),
        children: [
          GridView.count(
            crossAxisCount: 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            mainAxisSpacing: Gap.md,
            crossAxisSpacing: Gap.md,
            childAspectRatio: 1.35,
            children: [
              const StatTile(label: 'Total revenue', icon: Icons.currency_rupee_rounded, note: 'Available with payments'),
              StatTile(label: 'Total bookings', icon: Icons.event_available_rounded, value: '${d.totalBookings}'),
              const StatTile(label: 'Avg. utilization', icon: Icons.pie_chart_outline_rounded, note: 'Available with online booking'),
              StatTile(
                label: 'Avg. rating',
                icon: Icons.star_rounded,
                value: d.averageRating == null ? null : formatRating(d.averageRating!),
                note: d.averageRating == null ? 'No ratings yet' : '${d.ratingsCount} ratings',
              ),
            ],
          ),
          const SectionHeader('Your venues'),
          Row(children: [
            Expanded(child: StatTile(label: 'Published', icon: Icons.public_rounded, value: '${d.venuesPublished}')),
            const SizedBox(width: Gap.md),
            Expanded(child: StatTile(label: 'Drafts', icon: Icons.edit_note_rounded, value: '${d.venuesDraft}')),
          ]),
          const SectionHeader('Monthly revenue'),
          UnavailableCard(title: 'Not available yet', message: d.monthlyRevenue.message, icon: Icons.bar_chart_rounded),
          const SectionHeader('Booking overview'),
          Row(children: [
            Expanded(child: StatTile(label: 'Upcoming', icon: Icons.upcoming_outlined, value: '${d.bookingOverview.upcoming}')),
            const SizedBox(width: Gap.md),
            Expanded(child: StatTile(label: 'Completed', icon: Icons.task_alt_rounded, value: '${d.bookingOverview.completed}')),
            const SizedBox(width: Gap.md),
            Expanded(child: StatTile(label: 'Cancelled', icon: Icons.event_busy_outlined, value: '${d.bookingOverview.cancelled}')),
          ]),
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

class _PerformanceRow extends StatelessWidget {
  const _PerformanceRow({required this.v});
  final PerformanceVenue v;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: Gap.md),
      child: ListTile(
        onTap: () => context.push('/owner/venues/${v.venueId}'),
        leading: SizedBox(width: 52, height: 52, child: ZNetworkImage(url: v.coverImageUrl, borderRadius: 12)),
        title: Text(v.name, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w700)),
        subtitle: RatingText(rating: v.ratingAvg, count: v.ratingCount),
        trailing: StatusChip(v.status),
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
      leading: CircleAvatar(
        backgroundColor: Theme.of(context).colorScheme.primaryContainer,
        child: Icon(iconForNotification(n.type), color: Theme.of(context).colorScheme.primary, size: 20),
      ),
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
        GridView.count(
          crossAxisCount: 2,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          mainAxisSpacing: Gap.md,
          crossAxisSpacing: Gap.md,
          childAspectRatio: 1.35,
          children: List.generate(4, (_) => const ShimmerBox(radius: Radii.card)),
        ),
        const SizedBox(height: Gap.xl),
        const ShimmerBox(height: 72, radius: Radii.card),
        const SizedBox(height: Gap.md),
        const ShimmerBox(height: 72, radius: Radii.card),
      ],
    );
  }
}
