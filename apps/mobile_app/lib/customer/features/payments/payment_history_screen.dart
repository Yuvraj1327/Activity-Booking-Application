import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:go_router/go_router.dart';

import 'package:zuruv/core/constants/tokens.dart';
import 'package:zuruv/core/network/api_helpers.dart';
import 'package:zuruv/customer/core/utils/dates.dart';
import 'package:zuruv/customer/core/utils/format.dart';
import 'package:zuruv/customer/shared/models/payment.dart';
import 'package:zuruv/customer/shared/repositories/payment_repository.dart';
import 'package:zuruv/customer/shared/widgets/common_widgets.dart';
import 'package:zuruv/customer/features/booking/booking_providers.dart';

final paymentHistoryProvider = FutureProvider.autoDispose<PaymentPageData>((ref) {
  ref.watch(bookingsRevisionProvider); // reload after a payment changes something
  return ref.watch(paymentRepositoryProvider).history(offset: 0, limit: 50);
});

class PaymentHistoryScreen extends ConsumerWidget {
  const PaymentHistoryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final history = ref.watch(paymentHistoryProvider);
    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          tooltip: 'Back',
          onPressed: () => context.pop(),
          icon: const Icon(Icons.arrow_back_rounded),
        ),
        title: const Text('Payment history'),
      ),
      body: history.when(
        loading: () => const LoadingView(),
        error: (e, _) => ErrorView(message: errorMessage(e), onRetry: () => ref.invalidate(paymentHistoryProvider)),
        data: (page) {
          if (page.items.isEmpty) {
            return const EmptyState(
              icon: Icons.receipt_long_outlined,
              title: 'No payments yet',
              message: 'Payments for your bookings will appear here.',
            );
          }
          return RefreshIndicator(
            onRefresh: () async => ref.invalidate(paymentHistoryProvider),
            child: ListView.separated(
              padding: const EdgeInsets.all(Gap.page),
              itemCount: page.items.length,
              separatorBuilder: (_, __) => const Divider(height: Gap.xl),
              itemBuilder: (context, i) => _PaymentTile(payment: page.items[i]),
            ),
          );
        },
      ),
    );
  }
}

class _PaymentTile extends StatelessWidget {
  const _PaymentTile({required this.payment});

  final PaymentInfo payment;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final p = payment;
    return InkWell(
      onTap: () => context.push('/bookings/${p.bookingId}'),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(p.venueName, style: theme.textTheme.titleSmall),
            const SizedBox(height: 2),
            Text('${p.resourceName} · ${p.bookingCode}', style: theme.textTheme.bodySmall),
            const SizedBox(height: 2),
            Text(clockTime((p.capturedAt ?? p.createdAt).toLocal()), style: theme.textTheme.bodySmall),
          ]),
        ),
        Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
          Text(formatMoney(p.amountPaise, currency: p.currency), style: theme.textTheme.titleSmall),
          const SizedBox(height: 2),
          Text(
            p.needsReview ? 'Under review' : paymentStatusLabel(p.status),
            style: theme.textTheme.bodySmall?.copyWith(
              color: p.status == 'captured' && !p.needsReview ? ZuruvColors.success : (p.isFailed ? ZuruvColors.error : null),
            ),
          ),
        ]),
      ]),
    );
  }
}
