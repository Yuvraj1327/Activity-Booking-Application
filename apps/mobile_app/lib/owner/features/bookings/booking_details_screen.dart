import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';

import 'package:zuruv/core/constants/tokens.dart';
import 'package:zuruv/core/network/api_helpers.dart';
import 'package:zuruv/owner/core/utils/format.dart';
import 'package:zuruv/owner/shared/models/models.dart';
import 'package:zuruv/owner/shared/repositories/owner_repository.dart';
import 'package:zuruv/owner/shared/widgets/common_widgets.dart';

final bookingDetailProvider = FutureProvider.autoDispose.family<OwnerBooking, String>(
  (ref, id) => ref.watch(ownerRepositoryProvider).booking(id),
);

/// One booking at the owner's venue: ID, customer name, court, date, time, duration, amount,
/// payment and booking status, and the status history. Read-only: no status changes are offered
/// because owner-side cancellation/confirmation rules are not decided yet.
class BookingDetailsScreen extends ConsumerWidget {
  const BookingDetailsScreen({super.key, required this.bookingId});
  final String bookingId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final detail = ref.watch(bookingDetailProvider(bookingId));
    return Scaffold(
      appBar: AppBar(title: const Text('Booking details')),
      body: detail.when(
        loading: () => const LoadingView(),
        error: (e, _) => e is ApiException && e.statusCode == 404
            ? const EmptyState(icon: Icons.receipt_long_outlined, title: 'Booking not found', message: 'It may belong to another account or no longer exist.')
            : ErrorView(message: errorMessage(e), onRetry: () => ref.invalidate(bookingDetailProvider(bookingId))),
        data: (b) {
          final theme = Theme.of(context);
          Widget line(String k, String v) => Padding(
                padding: const EdgeInsets.symmetric(vertical: 6),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(k, style: theme.textTheme.bodySmall),
                    const SizedBox(width: Gap.lg),
                    Flexible(child: Text(v, textAlign: TextAlign.end)),
                  ],
                ),
              );
          return ListView(
            padding: const EdgeInsets.all(Gap.page),
            children: [
              Text(b.customerName, style: theme.textTheme.titleLarge),
              const SizedBox(height: 4),
              Text('Booking ${b.code}', style: theme.textTheme.bodySmall),
              const SizedBox(height: Gap.xl),
              line('Venue', b.venueName),
              line('Court', b.courtName),
              line('Date', formatDate(DateTime.parse(b.bookingDate))),
              line('Time', '${b.localStart} – ${b.localEnd}'),
              line('Duration', '${b.durationMinutes} min'),
              line('Amount', formatMoney(b.totalAmountPaise, currency: b.currency)),
              line('Payment', switch (b.paymentStatus) { 'paid' => 'Paid', 'pending' => 'Payment pending', 'failed' => 'Payment failed', 'refunded' => 'Refunded', _ => 'Not paid' }),
              line('Status', b.statusLabel),
              if (b.history.isNotEmpty) ...[
                const SizedBox(height: Gap.xxl),
                Text('History', style: theme.textTheme.titleMedium),
                const SizedBox(height: Gap.sm),
                for (final e in b.history)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    child: Row(children: [
                      const Icon(Icons.circle, size: 8),
                      const SizedBox(width: Gap.sm),
                      Expanded(child: Text(bookingStatusLabel(e.toStatus))),
                      Text(timeAgo(e.createdAt), style: theme.textTheme.bodySmall),
                    ]),
                  ),
              ],
            ],
          );
        },
      ),
    );
  }
}
