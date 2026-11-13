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
import 'package:zuruv/customer/features/reviews/review_widgets.dart';
import 'package:zuruv/customer/features/bookings/bookings_screen.dart';

class BookingDetailsScreen extends ConsumerStatefulWidget {
  const BookingDetailsScreen({super.key, required this.bookingId});

  final String bookingId;

  @override
  ConsumerState<BookingDetailsScreen> createState() => _BookingDetailsScreenState();
}

class _BookingDetailsScreenState extends ConsumerState<BookingDetailsScreen> {
  bool _cancelling = false;

  Future<void> _cancel(Booking b) async {
    final repo = ref.read(bookingRepositoryProvider);
    setState(() => _cancelling = true);
    try {
      // Ask the server first: the rules (notice period, paid bookings) live on the backend.
      final preview = await repo.cancellationPreview(b.id);
      if (!mounted) return;
      if (!preview.canCancel) {
        await showDialog<void>(
          context: context,
          builder: (_) => AlertDialog(
            title: const Text('Cannot cancel'),
            content: Text(preview.message),
            actions: [TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('OK'))],
          ),
        );
        return;
      }
      final reason = TextEditingController();
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (_) => AlertDialog(
          title: const Text('Cancel this booking?'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(preview.message),
              const SizedBox(height: Gap.md),
              TextField(
                controller: reason,
                maxLength: 300,
                decoration: const InputDecoration(labelText: 'Reason (optional)'),
              ),
            ],
          ),
          actions: [
            TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text('Keep booking')),
            FilledButton(onPressed: () => Navigator.of(context).pop(true), child: const Text('Cancel booking')),
          ],
        ),
      );
      if (confirmed != true || !mounted) return;
      await repo.cancel(b.id, reason: reason.text);
      ref.invalidate(bookingDetailProvider(b.id));
      ref.read(bookingsRevisionProvider.notifier).state++;
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Booking cancelled.')));
      }
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(errorMessage(e))));
      ref.invalidate(bookingDetailProvider(b.id));
    } finally {
      if (mounted) setState(() => _cancelling = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final detail = ref.watch(bookingDetailProvider(widget.bookingId));
    return Scaffold(
      appBar: AppBar(title: const Text('Booking details')),
      body: detail.when(
        loading: () => const LoadingView(),
        error: (e, _) {
          final missing = e is ApiException && e.statusCode == 404;
          return missing
              ? const EmptyState(icon: Icons.event_busy_outlined, title: 'Booking not found')
              : ErrorView(message: errorMessage(e), onRetry: () => ref.invalidate(bookingDetailProvider(widget.bookingId)));
        },
        data: (b) => _Body(booking: b, cancelling: _cancelling, onCancel: () => _cancel(b)),
      ),
    );
  }
}

class _Body extends StatelessWidget {
  const _Body({required this.booking, required this.cancelling, required this.onCancel});

  final Booking booking;
  final bool cancelling;
  final VoidCallback onCancel;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final b = booking;
    return ListView(
      padding: const EdgeInsets.all(Gap.page),
      children: [
        Row(children: [
          Expanded(child: Text(b.venueName, style: theme.textTheme.titleLarge)),
          StatusChip(booking: b),
        ]),
        const SizedBox(height: 4),
        Text('Booking ${b.code}', style: theme.textTheme.bodySmall),
        const SizedBox(height: Gap.xl),
        _Line('Court', b.resourceName),
        _Line('Date', prettyDate(b.bookingDate)),
        _Line('Time', '${b.localStart} – ${b.localEnd}'),
        _Line('Duration', prettyDuration(b.durationMinutes)),
        _Line('Total', formatMoney(b.totalAmountPaise, currency: b.currency)),
        _Line('Payment', _paymentLabel(b.paymentStatus)),
        if (b.isHold && b.expiresAt != null)
          Padding(
            padding: const EdgeInsets.only(top: Gap.md),
            child: Text(
              'Your slot is held until ${clockTime(b.expiresAt!.toLocal())}. Complete the payment to '
              'confirm the booking.',
              style: theme.textTheme.bodySmall,
            ),
          ),
        if (b.isHold) ...[
          const SizedBox(height: Gap.lg),
          FilledButton(
            onPressed: () => context.push('/bookings/${b.id}/pay'),
            child: Text(b.status == 'payment_failed' ? 'Retry payment' : 'Pay ${formatMoney(b.totalAmountPaise, currency: b.currency)}'),
          ),
        ],
        if (b.cancelReason != null) _Line('Cancel reason', b.cancelReason!),
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
                Expanded(child: Text(_eventLabel(e), style: theme.textTheme.bodyMedium)),
                Text(_clock(e.createdAt.toLocal()), style: theme.textTheme.bodySmall),
              ]),
            ),
        ],
        if (b.status == 'completed') BookingReviewCard(bookingId: b.id),
        if (b.canCancel) ...[
          const SizedBox(height: Gap.xxl),
          OutlinedButton(
            onPressed: cancelling ? null : onCancel,
            child: cancelling
                ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('Cancel booking'),
          ),
        ],
      ],
    );
  }

  static String _clock(DateTime t) => clockTime(t);

  static String _paymentLabel(String s) => switch (s) {
        'paid' => 'Paid',
        'pending' => 'Payment pending',
        'failed' => 'Payment failed',
        'refunded' => 'Refunded',
        _ => 'Not paid',
      };

  static String _eventLabel(StatusEvent e) => statusLabelFor(e.toStatus);
}

class _Line extends StatelessWidget {
  const _Line(this.label, this.value);

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: theme.textTheme.bodySmall),
          const SizedBox(width: Gap.lg),
          Flexible(child: Text(value, style: theme.textTheme.bodyMedium, textAlign: TextAlign.end)),
        ],
      ),
    );
  }
}
