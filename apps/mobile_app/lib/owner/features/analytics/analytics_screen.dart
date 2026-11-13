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

/// Date range for analytics. Value-equal so it can key an autoDispose family.
class DateRangeQuery {
  const DateRangeQuery(this.from, this.to);
  final String from; // yyyy-MM-dd
  final String to;
  @override
  bool operator ==(Object other) => other is DateRangeQuery && other.from == from && other.to == to;
  @override
  int get hashCode => Object.hash(from, to);
}

final analyticsRangeProvider = StateProvider.autoDispose<DateRangeQuery>((ref) {
  final now = DateTime.now();
  return DateRangeQuery(apiDate(now.subtract(const Duration(days: 29))), apiDate(now));
});

final analyticsProvider = FutureProvider.autoDispose<Analytics>((ref) {
  final r = ref.watch(analyticsRangeProvider);
  return ref.watch(ownerRepositoryProvider).analytics(from: r.from, to: r.to);
});

/// Analytics with a date filter. Venue ratings are real; booking, revenue and utilization
/// analytics depend on Steps 6 and 7 and are shown as unavailable.
class AnalyticsScreen extends ConsumerWidget {
  const AnalyticsScreen({super.key});

  Future<void> _pickRange(BuildContext context, WidgetRef ref) async {
    final range = ref.read(analyticsRangeProvider);
    final picked = await showDateRangePicker(
      context: context,
      firstDate: DateTime(2024),
      lastDate: DateTime.now(),
      initialDateRange: DateTimeRange(start: DateTime.parse(range.from), end: DateTime.parse(range.to)),
    );
    if (picked != null) {
      ref.read(analyticsRangeProvider.notifier).state = DateRangeQuery(apiDate(picked.start), apiDate(picked.end));
    }
  }

  void _preset(WidgetRef ref, int days) {
    final now = DateTime.now();
    ref.read(analyticsRangeProvider.notifier).state = DateRangeQuery(apiDate(now.subtract(Duration(days: days - 1))), apiDate(now));
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final range = ref.watch(analyticsRangeProvider);
    final data = ref.watch(analyticsProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Analytics')),
      body: ResponsivePage(
        maxWidth: 720,
        child: ListView(
          padding: const EdgeInsets.only(top: 8, bottom: 32),
          children: [
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                ActionChip(label: const Text('7 days'), onPressed: () => _preset(ref, 7)),
                ActionChip(label: const Text('30 days'), onPressed: () => _preset(ref, 30)),
                ActionChip(label: const Text('90 days'), onPressed: () => _preset(ref, 90)),
                ActionChip(
                  avatar: const Icon(Icons.date_range_rounded, size: 18),
                  label: Text('${formatDate(DateTime.parse(range.from))} – ${formatDate(DateTime.parse(range.to))}'),
                  onPressed: () => _pickRange(context, ref),
                ),
              ],
            ),
            data.when(
              loading: () => const Padding(padding: EdgeInsets.only(top: 80), child: LoadingView()),
              error: (e, _) => SizedBox(height: 360, child: ErrorView.fromError(e, onRetry: () => ref.invalidate(analyticsProvider))),
              data: (a) => Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const SectionHeader('Bookings'),
                  UnavailableCard(title: 'Total bookings', message: a.totalBookings.message, icon: Icons.event_available_rounded),
                  const SizedBox(height: Gap.md),
                  UnavailableCard(title: 'Booking trends', message: a.bookingTrends.message, icon: Icons.show_chart_rounded),
                  const SectionHeader('Revenue & utilization'),
                  UnavailableCard(title: 'Revenue', message: a.revenue.message, icon: Icons.currency_rupee_rounded),
                  const SizedBox(height: Gap.md),
                  UnavailableCard(title: 'Utilization', message: a.utilization.message, icon: Icons.pie_chart_outline_rounded),
                  const SizedBox(height: Gap.md),
                  UnavailableCard(title: 'Popular time slots', message: a.popularSlots.message, icon: Icons.schedule_rounded),
                  const SectionHeader('Venue performance'),
                  if (a.performance.isEmpty)
                    const UnavailableCard(title: 'No venues yet', message: 'Add a venue to see how it performs.', icon: Icons.storefront_outlined)
                  else
                    for (final v in a.performance) _VenueRow(v: v),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _VenueRow extends StatelessWidget {
  const _VenueRow({required this.v});
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
