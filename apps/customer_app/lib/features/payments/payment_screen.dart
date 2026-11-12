import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:go_router/go_router.dart';

import '../../core/constants/tokens.dart';
import '../../core/network/api_helpers.dart';
import '../../core/utils/dates.dart';
import '../../core/utils/format.dart';
import '../../shared/models/booking.dart';
import '../../shared/widgets/common_widgets.dart';
import '../booking/booking_providers.dart';
import 'payment_flow.dart';

const Color _warning = Color(0xFFE08A00);

/// Pay for one held booking. The screen shows "Payment successful / Booking confirmed" ONLY after
/// the backend reports the payment verified and the booking confirmed.
class PaymentScreen extends ConsumerWidget {
  const PaymentScreen({super.key, required this.bookingId});

  final String bookingId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final detail = ref.watch(bookingDetailProvider(bookingId));
    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          tooltip: 'Back',
          onPressed: () => context.canPop() ? context.pop() : context.go('/bookings'),
          icon: const Icon(Icons.arrow_back_rounded),
        ),
        title: const Text('Payment'),
      ),
      body: detail.when(
        loading: () => const LoadingView(),
        error: (e, _) => ErrorView(message: errorMessage(e), onRetry: () => ref.invalidate(bookingDetailProvider(bookingId))),
        data: (b) => _PayBody(booking: b),
      ),
    );
  }
}

class _PayBody extends ConsumerWidget {
  const _PayBody({required this.booking});

  final Booking booking;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final flow = ref.watch(paymentFlowProvider(booking.id));
    final controller = ref.read(paymentFlowProvider(booking.id).notifier);
    final b = booking;
    final alreadyConfirmed = b.status == 'confirmed' && b.paymentStatus == 'paid';
    final phase = alreadyConfirmed ? PayPhase.success : flow.phase;
    return ListView(
      padding: const EdgeInsets.all(Gap.page),
      children: [
        Text(b.venueName, style: theme.textTheme.titleLarge),
        const SizedBox(height: 4),
        Text('Booking ${b.code}', style: theme.textTheme.bodySmall),
        const SizedBox(height: Gap.lg),
        _Line('Court', b.resourceName),
        _Line('Date', prettyDate(b.bookingDate)),
        _Line('Time', '${b.localStart} – ${b.localEnd}'),
        const Divider(height: Gap.xxl),
        _Line('Amount to pay', formatMoney(b.totalAmountPaise, currency: b.currency), bold: true),
        if (b.isHold && b.expiresAt != null && phase != PayPhase.success)
          Padding(
            padding: const EdgeInsets.only(top: Gap.sm),
            child: Text('Your slot is held until ${clockTime(b.expiresAt!.toLocal())}.', style: theme.textTheme.bodySmall),
          ),
        const SizedBox(height: Gap.xl),
        _StateCard(phase: phase, message: flow.message),
        const SizedBox(height: Gap.xl),
        ..._actions(context, ref, phase, controller),
      ],
    );
  }

  List<Widget> _actions(BuildContext context, WidgetRef ref, PayPhase phase, PaymentFlowController controller) {
    final total = formatMoney(booking.totalAmountPaise, currency: booking.currency);
    Widget primary(String label, VoidCallback? onPressed, {bool busy = false}) => SizedBox(
          width: double.infinity,
          child: FilledButton(
            onPressed: onPressed,
            child: busy ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2)) : Text(label),
          ),
        );
    Widget secondary(String label, VoidCallback onPressed) =>
        SizedBox(width: double.infinity, child: OutlinedButton(onPressed: onPressed, child: Text(label)));

    switch (phase) {
      case PayPhase.idle:
        return [primary('Pay $total', controller.start)];
      case PayPhase.creatingOrder:
      case PayPhase.checkout:
        return [primary('Pay $total', null, busy: true)];
      case PayPhase.verifying:
        return [primary('Pay $total', null, busy: true)];
      case PayPhase.pending:
        return [
          primary('Check again', controller.checkAgain),
          const SizedBox(height: Gap.md),
          secondary('View my bookings', () => context.go('/bookings')),
        ];
      case PayPhase.success:
        return [
          primary('View booking', () => context.pushReplacement('/bookings/${booking.id}')),
        ];
      case PayPhase.failed:
      case PayPhase.cancelled:
        return [
          primary('Try again', controller.start),
          const SizedBox(height: Gap.md),
          secondary('View my bookings', () => context.go('/bookings')),
        ];
      case PayPhase.offline:
        return [primary('Try again', controller.start)];
      case PayPhase.error:
        return [primary('Try again', controller.start)];
      case PayPhase.expired:
        return [primary('Book again', () => context.go('/venues/${booking.venueId}/book'))];
      case PayPhase.needsReview:
        return [secondary('View my bookings', () => context.go('/bookings'))];
    }
  }
}

class _StateCard extends StatelessWidget {
  const _StateCard({required this.phase, this.message});

  final PayPhase phase;
  final String? message;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final (IconData icon, Color color, String title, String body) = switch (phase) {
      PayPhase.idle => (Icons.lock_outline_rounded, theme.colorScheme.primary, 'Secure payment', 'Pay with UPI, card, net banking or wallet.'),
      PayPhase.creatingOrder => (Icons.hourglass_top_rounded, theme.colorScheme.primary, 'Processing', 'Preparing your payment…'),
      PayPhase.checkout => (Icons.hourglass_top_rounded, theme.colorScheme.primary, 'Processing', 'Complete the payment in the payment window.'),
      PayPhase.verifying => (Icons.sync_rounded, theme.colorScheme.primary, 'Verification in progress', 'Please wait while we confirm your payment.'),
      PayPhase.pending => (Icons.schedule_rounded, _warning, 'Payment pending', 'We are waiting for the bank to confirm your payment.'),
      PayPhase.success => (Icons.check_circle_rounded, ZuruvColors.success, 'Payment successful', 'Your booking is confirmed.'),
      PayPhase.failed => (Icons.error_outline_rounded, theme.colorScheme.error, 'Payment failed', 'No booking was confirmed. You can try again.'),
      PayPhase.cancelled => (Icons.cancel_outlined, _warning, 'Payment cancelled', 'You closed the payment window. Your slot is held for a short time.'),
      PayPhase.expired => (Icons.timer_off_outlined, theme.colorScheme.error, 'Time ran out', 'The slot hold expired before payment.'),
      PayPhase.needsReview => (Icons.support_agent_rounded, _warning, 'Payment received', 'We could not confirm the booking automatically.'),
      PayPhase.offline => (Icons.wifi_off_rounded, _warning, 'No connection', 'We could not reach the server.'),
      PayPhase.error => (Icons.error_outline_rounded, theme.colorScheme.error, 'Something went wrong', 'Please try again.'),
    };
    return Container(
      padding: const EdgeInsets.all(Gap.lg),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(Radii.card),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Icon(icon, color: color, size: 28),
        const SizedBox(width: Gap.md),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title, style: theme.textTheme.titleMedium),
            const SizedBox(height: 4),
            Text(message ?? body, style: theme.textTheme.bodyMedium),
          ]),
        ),
      ]),
    );
  }
}

class _Line extends StatelessWidget {
  const _Line(this.label, this.value, {this.bold = false});

  final String label;
  final String value;
  final bool bold;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: theme.textTheme.bodySmall),
          const SizedBox(width: Gap.lg),
          Flexible(child: Text(value, style: bold ? theme.textTheme.titleMedium : theme.textTheme.bodyMedium, textAlign: TextAlign.end)),
        ],
      ),
    );
  }
}
