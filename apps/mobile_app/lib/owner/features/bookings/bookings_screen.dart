import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:go_router/go_router.dart';

import 'package:zuruv/core/constants/tokens.dart';
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
          bottom: TabBar(tabs: [for (final t in _tabs) Tab(text: t.$1)]),
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
          final b = _items[i];
          return Card(
            child: InkWell(
              borderRadius: BorderRadius.circular(Radii.card),
              onTap: () => context.push('/owner/bookings/${b.id}'),
              child: Padding(
                padding: const EdgeInsets.all(Gap.lg),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(children: [
                      Expanded(child: Text(b.customerName, style: Theme.of(context).textTheme.titleMedium)),
                      Text(b.statusLabel, style: Theme.of(context).textTheme.labelMedium),
                    ]),
                    const SizedBox(height: 4),
                    Text('${b.venueName} · ${b.courtName}', style: Theme.of(context).textTheme.bodySmall),
                    const SizedBox(height: Gap.sm),
                    Text('${formatDate(DateTime.parse(b.bookingDate))} · ${b.localStart}–${b.localEnd}'),
                    const SizedBox(height: 4),
                    Text('${b.code} · ${formatMoney(b.totalAmountPaise, currency: b.currency)}', style: Theme.of(context).textTheme.bodySmall),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}
