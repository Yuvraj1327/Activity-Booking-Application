import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:go_router/go_router.dart';

import 'package:zuruv/core/constants/tokens.dart';
import 'package:zuruv/core/network/api_helpers.dart';
import 'package:zuruv/customer/core/utils/dates.dart';
import 'package:zuruv/customer/core/utils/format.dart';
import 'package:zuruv/customer/shared/models/booking.dart';
import 'package:zuruv/customer/shared/repositories/booking_repository.dart';
import 'package:zuruv/customer/shared/widgets/common_widgets.dart';
import 'package:zuruv/customer/features/booking/booking_providers.dart';

/// My Bookings: Upcoming / Past / Cancelled, all straight from the backend.
class BookingsScreen extends StatelessWidget {
  const BookingsScreen({super.key});

  static const _tabs = ['Upcoming', 'Past', 'Cancelled'];

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 3,
      child: Scaffold(
        appBar: AppBar(title: Text('My Bookings', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontSize: 26))),
        body: const Column(
          children: [
            _PillTabs(labels: _tabs),
            Expanded(
              child: TabBarView(children: [
                BookingList(bucket: 'upcoming'),
                BookingList(bucket: 'past'),
                BookingList(bucket: 'cancelled'),
              ]),
            ),
          ],
        ),
      ),
    );
  }
}

/// Rounded pill switcher bound to the surrounding [DefaultTabController].
class _PillTabs extends StatelessWidget {
  const _PillTabs({required this.labels});

  final List<String> labels;

  @override
  Widget build(BuildContext context) {
    final controller = DefaultTabController.of(context);
    final theme = Theme.of(context);
    return AnimatedBuilder(
      animation: controller.animation!,
      builder: (context, _) {
        final selected = controller.index;
        return SizedBox(
          height: 52,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: Gap.page, vertical: 6),
            itemCount: labels.length,
            separatorBuilder: (_, __) => const SizedBox(width: 10),
            itemBuilder: (_, i) {
              final on = i == selected;
              return Semantics(
                button: true,
                selected: on,
                child: InkWell(
                  borderRadius: BorderRadius.circular(20),
                  onTap: () => controller.animateTo(i),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 20),
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: on ? theme.colorScheme.primary : theme.colorScheme.surface,
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: on ? theme.colorScheme.primary : theme.colorScheme.outline),
                    ),
                    child: Text(
                      labels[i],
                      style: TextStyle(fontWeight: FontWeight.w600, color: on ? theme.colorScheme.onPrimary : theme.colorScheme.onSurface),
                    ),
                  ),
                ),
              );
            },
          ),
        );
      },
    );
  }
}

class BookingList extends ConsumerStatefulWidget {
  const BookingList({super.key, required this.bucket});

  final String bucket;

  @override
  ConsumerState<BookingList> createState() => _BookingListState();
}

class _BookingListState extends ConsumerState<BookingList> with AutomaticKeepAliveClientMixin {
  final List<Booking> _items = [];
  bool _loading = true;
  bool _loadingMore = false;
  bool _hasMore = false;
  Object? _error;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final page = await ref.read(bookingRepositoryProvider).list(widget.bucket, offset: 0);
      if (!mounted) return;
      setState(() {
        _items
          ..clear()
          ..addAll(page.items);
        _hasMore = page.hasMore;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e;
        _loading = false;
      });
    }
  }

  Future<void> _more() async {
    if (_loadingMore) return;
    setState(() => _loadingMore = true);
    try {
      final page = await ref.read(bookingRepositoryProvider).list(widget.bucket, offset: _items.length);
      if (!mounted) return;
      setState(() {
        _items.addAll(page.items);
        _hasMore = page.hasMore;
        _loadingMore = false;
      });
    } catch (_) {
      if (mounted) setState(() => _loadingMore = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    ref.listen<int>(bookingsRevisionProvider, (_, __) => _load());
    if (_loading) return const LoadingView();
    if (_error != null) return ErrorView(message: errorMessage(_error!), onRetry: _load);
    if (_items.isEmpty) {
      return EmptyState(
        icon: Icons.calendar_month_outlined,
        title: switch (widget.bucket) {
          'upcoming' => 'No upcoming bookings',
          'past' => 'No past bookings',
          _ => 'No cancelled bookings',
        },
        message: widget.bucket == 'upcoming' ? 'Find a venue and book your next game.' : null,
        action: widget.bucket == 'upcoming'
            ? OutlinedButton(
                style: OutlinedButton.styleFrom(minimumSize: const Size(180, 48)),
                onPressed: () => context.go('/explore'),
                child: const Text('Explore venues'),
              )
            : null,
      );
    }
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.separated(
        padding: const EdgeInsets.all(Gap.page),
        itemCount: _items.length + (_hasMore ? 1 : 0),
        separatorBuilder: (_, __) => const SizedBox(height: Gap.md),
        itemBuilder: (_, i) {
          if (i == _items.length) {
            return Center(
              child: _loadingMore
                  ? const Padding(padding: EdgeInsets.all(12), child: CircularProgressIndicator())
                  : TextButton(onPressed: _more, child: const Text('Load more')),
            );
          }
          return BookingCard(
            booking: _items[i],
            onTap: () async {
              await context.push('/bookings/${_items[i].id}');
              if (mounted) _load(); // the booking may have been cancelled meanwhile
            },
          );
        },
      ),
    );
  }
}

class BookingCard extends StatelessWidget {
  const BookingCard({super.key, required this.booking, required this.onTap});

  final Booking booking;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final muted = theme.colorScheme.onSurfaceVariant;
    Widget line(IconData icon, String text) => Padding(
          padding: const EdgeInsets.only(top: 4),
          child: Row(children: [
            Icon(icon, size: 15, color: muted),
            const SizedBox(width: 6),
            Expanded(child: Text(text, style: theme.textTheme.bodySmall, maxLines: 1, overflow: TextOverflow.ellipsis)),
          ]),
        );
    return Container(
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        borderRadius: BorderRadius.circular(Radii.card),
        border: Border.all(color: theme.colorScheme.outline),
        boxShadow: Shadows.card,
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(Radii.card),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              Container(
                width: 76,
                height: 76,
                decoration: BoxDecoration(color: theme.colorScheme.primaryContainer, borderRadius: BorderRadius.circular(14)),
                child: Icon(Icons.sports_score_rounded, size: 32, color: theme.colorScheme.primary),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(booking.venueName, style: theme.textTheme.titleMedium, maxLines: 1, overflow: TextOverflow.ellipsis),
                    line(Icons.sports_rounded, booking.resourceName),
                    line(Icons.calendar_today_outlined, prettyDate(booking.bookingDate)),
                    line(Icons.schedule_rounded, '${booking.localStart} – ${booking.localEnd}'),
                    const SizedBox(height: 8),
                    Row(children: [
                      StatusChip(booking: booking),
                      const SizedBox(width: 8),
                      Text(formatMoney(booking.totalAmountPaise, currency: booking.currency), style: theme.textTheme.titleSmall),
                    ]),
                  ],
                ),
              ),
              Icon(Icons.chevron_right_rounded, color: muted),
            ],
          ),
        ),
      ),
    );
  }
}

class StatusChip extends StatelessWidget {
  const StatusChip({super.key, required this.booking});

  final Booking booking;

  @override
  Widget build(BuildContext context) {
    final good = booking.status == 'confirmed' || booking.status == 'completed';
    final bad = booking.status == 'payment_failed' || booking.status.startsWith('cancelled') || booking.status == 'expired';
    final color = good ? ZuruvColors.success : (bad ? ZuruvColors.error : ZuruvColors.textSecondary);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: color.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(Radii.chip)),
      child: Text(booking.statusLabel, style: Theme.of(context).textTheme.labelSmall?.copyWith(color: color)),
    );
  }
}
