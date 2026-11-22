import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:go_router/go_router.dart';

import 'package:zuruv/core/constants/tokens.dart';
import 'package:zuruv/core/theme/owner_theme.dart';
import 'package:zuruv/core/network/api_helpers.dart';
import 'package:zuruv/owner/core/utils/format.dart';
import 'package:zuruv/owner/shared/models/models.dart';
import 'package:zuruv/owner/shared/repositories/owner_repository.dart';
import 'package:zuruv/owner/shared/widgets/common_widgets.dart';

/// Bookings at the owner's venues: Upcoming / Past / Cancelled. Read-only: owners cannot change
/// a booking's status (cancellation by owners is an open business decision).
/// Unpaid holds are not shown; a booking appears once it is confirmed.
class BookingsScreen extends StatelessWidget {
  const BookingsScreen({super.key});

  static const _tabs = [('Upcoming', 'upcoming'), ('Past', 'past'), ('Cancelled', 'cancelled')];

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: _tabs.length,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Bookings'),
          titleSpacing: Gap.page,
          bottom: PreferredSize(
            preferredSize: const Size.fromHeight(56),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(Gap.page, 4, Gap.page, 10),
              child: Container(
                decoration: BoxDecoration(color: OwnerColors.tint, borderRadius: BorderRadius.circular(14)),
                padding: const EdgeInsets.all(4),
                child: TabBar(
                  dividerColor: Colors.transparent,
                  indicatorSize: TabBarIndicatorSize.tab,
                  indicator: BoxDecoration(color: Theme.of(context).colorScheme.primary, borderRadius: BorderRadius.circular(10)),
                  labelColor: Colors.white,
                  unselectedLabelColor: Theme.of(context).colorScheme.primary,
                  labelStyle: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13.5),
                  splashBorderRadius: BorderRadius.circular(10),
                  tabs: [for (final t in _tabs) Tab(height: 38, text: t.$1)],
                ),
              ),
            ),
          ),
        ),
        body: TabBarView(children: [for (final t in _tabs) BookingBucket(bucket: t.$2)]),
      ),
    );
  }
}

class BookingBucket extends ConsumerStatefulWidget {
  const BookingBucket({super.key, required this.bucket});
  final String bucket;

  @override
  ConsumerState<BookingBucket> createState() => _BookingBucketState();
}

class _BookingBucketState extends ConsumerState<BookingBucket> with AutomaticKeepAliveClientMixin {
  final List<OwnerBooking> _items = [];
  bool _loading = true;
  bool _loadingMore = false;
  bool _hasMore = false;
  String? _error;

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
      final page = await ref.read(ownerRepositoryProvider).bookings(widget.bucket);
      if (!mounted) return;
      setState(() {
        _items
          ..clear()
          ..addAll(page.items);
        _hasMore = page.hasMore;
        _loading = false;
      });
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = errorMessage(e);
          _loading = false;
        });
      }
    }
  }

  Future<void> _more() async {
    setState(() => _loadingMore = true);
    try {
      final page = await ref.read(ownerRepositoryProvider).bookings(widget.bucket, offset: _items.length);
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
    if (_loading) return const LoadingView();
    if (_error != null) return ErrorView(message: _error!, onRetry: _load);
    if (_items.isEmpty) {
      return EmptyState(
        icon: Icons.event_busy_outlined,
        title: 'No ${widget.bucket} bookings yet',
        message: widget.bucket == 'upcoming'
            ? 'Confirmed bookings at your venues will appear here.'
            : 'Bookings that match will appear here.',
      );
    }
    // Flat list of rows: a date heading whenever the date changes, then the booking cards.
    final rows = <Object>[];
    String? lastDate;
    for (final b in _items) {
      if (b.bookingDate != lastDate) {
        rows.add(_dayLabel(b.bookingDate));
        lastDate = b.bookingDate;
      }
      rows.add(b);
    }
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.builder(
        padding: const EdgeInsets.fromLTRB(Gap.page, 0, Gap.page, Gap.xxl),
        itemCount: rows.length + (_hasMore ? 1 : 0),
        itemBuilder: (_, i) {
          if (i == rows.length) {
            return Center(
              child: _loadingMore
                  ? const Padding(padding: EdgeInsets.all(12), child: CircularProgressIndicator())
                  : TextButton(onPressed: _more, child: const Text('Load more')),
            );
          }
          final row = rows[i];
          if (row is String) {
            return Padding(
              padding: EdgeInsets.fromLTRB(2, i == 0 ? Gap.sm : Gap.xl, 0, Gap.sm),
              child: Text(row, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
            );
          }
          return Padding(padding: const EdgeInsets.only(bottom: Gap.md), child: _BookingCard(b: row as OwnerBooking));
        },
      ),
    );
  }
}

/// "Today", "Tomorrow", otherwise "26 Jan 2030".
String _dayLabel(String apiDate) {
  final d = DateTime.tryParse(apiDate);
  if (d == null) return apiDate;
  final now = DateTime.now();
  final today = DateTime(now.year, now.month, now.day);
  final diff = DateTime(d.year, d.month, d.day).difference(today).inDays;
  return switch (diff) {
    0 => 'Today',
    1 => 'Tomorrow',
    -1 => 'Yesterday',
    _ => formatDate(d),
  };
}

class _BookingCard extends StatelessWidget {
  const _BookingCard({required this.b});
  final OwnerBooking b;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final (fg, bg) = switch (b.status) {
      'confirmed' => (ZuruvColors.success, const Color(0xFFE6F7EE)),
      'completed' => (OwnerColors.blue, OwnerColors.tint),
      'pending_payment' || 'refund_pending' => (const Color(0xFFB26A00), const Color(0xFFFFF3E0)),
      'cancelled_by_customer' || 'cancelled_by_owner' || 'cancelled_by_admin' || 'payment_failed' || 'expired' => (ZuruvColors.error, const Color(0xFFFDE8EC)),
      _ => (ZuruvColors.textSecondary, const Color(0xFFF0F0F4)),
    };
    return OwnerCard(
      onTap: () => context.push('/owner/bookings/${b.id}'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            const IconBadge(Icons.sports_rounded, size: 44),
            const SizedBox(width: Gap.md),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(b.customerName, maxLines: 1, overflow: TextOverflow.ellipsis, style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
                const SizedBox(height: 2),
                Text('${b.venueName} · ${b.courtName}', maxLines: 1, overflow: TextOverflow.ellipsis, style: theme.textTheme.bodySmall?.copyWith(color: ZuruvColors.textSecondary)),
              ]),
            ),
            const SizedBox(width: Gap.sm),
            Flexible(
              flex: 0,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(20)),
                child: Text(b.statusLabel, maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: fg)),
              ),
            ),
          ]),
          const SizedBox(height: Gap.md),
          Row(children: [
            const Icon(Icons.schedule_rounded, size: 16, color: ZuruvColors.textSecondary),
            const SizedBox(width: 6),
            Expanded(
              child: Text('${time12(b.localStart)} – ${time12(b.localEnd)}', style: theme.textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600)),
            ),
            Text(formatMoney(b.totalAmountPaise, currency: b.currency), style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
          ]),
          const SizedBox(height: 4),
          Text(b.code, style: theme.textTheme.bodySmall?.copyWith(color: ZuruvColors.textSecondary)),
        ],
      ),
    );
  }
}
