import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:go_router/go_router.dart';

import '../../core/constants/tokens.dart';
import '../../core/utils/format.dart';
import '../../shared/models/models.dart';
import '../../shared/repositories/owner_repository.dart';
import '../../shared/widgets/common_widgets.dart';

final earningsProvider = FutureProvider.autoDispose<OwnerEarnings>((ref) => ref.watch(ownerRepositoryProvider).earnings());
final ownerPaymentsProvider =
    FutureProvider.autoDispose<OwnerPaymentPage>((ref) => ref.watch(ownerRepositoryProvider).payments());

/// Payments & Earnings. Shows ONLY confirmed facts: the gross amounts customers actually paid.
/// Commission, GST, deductions, net earnings, settlement timing and payouts are not shown as numbers
/// because those rules are not approved yet (the backend reports them as unavailable).
class EarningsScreen extends ConsumerWidget {
  const EarningsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final data = ref.watch(earningsProvider);
    final payments = ref.watch(ownerPaymentsProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Payments & Earnings')),
      body: data.when(
        loading: () => const LoadingView(),
        error: (e, _) => ErrorView.fromError(e, onRetry: () {
          ref.invalidate(earningsProvider);
          ref.invalidate(ownerPaymentsProvider);
        }),
        data: (e) => ResponsivePage(
          maxWidth: 720,
          child: RefreshIndicator(
            onRefresh: () async {
              ref.invalidate(earningsProvider);
              ref.invalidate(ownerPaymentsProvider);
            },
            child: ListView(
              padding: const EdgeInsets.only(top: 8, bottom: 32),
              children: [
                Row(children: [
                  Expanded(
                    child: StatTile(
                      label: 'Gross paid by customers',
                      icon: Icons.currency_rupee_rounded,
                      value: formatMoney(e.grossPaidPaise, currency: e.currency),
                    ),
                  ),
                  const SizedBox(width: Gap.md),
                  Expanded(
                    child: StatTile(label: 'Paid bookings', icon: Icons.receipt_long_rounded, value: '${e.paymentsCount}'),
                  ),
                ]),
                const SizedBox(height: Gap.sm),
                Text(
                  'Gross amounts only. Platform fees, tax and net earnings are not calculated yet.',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(color: ZuruvColors.textSecondary),
                ),
                if (e.byVenue.isNotEmpty) ...[
                  const SectionHeader('By venue'),
                  for (final v in e.byVenue)
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      title: Text(v.venueName),
                      subtitle: Text('${v.payments} paid booking${v.payments == 1 ? '' : 's'}'),
                      trailing: Text(formatMoney(v.grossPaidPaise, currency: e.currency), style: Theme.of(context).textTheme.titleSmall),
                    ),
                ],
                const SectionHeader('Payment history'),
                payments.when(
                  loading: () => const Padding(padding: EdgeInsets.all(Gap.lg), child: Center(child: CircularProgressIndicator())),
                  error: (err, _) => UnavailableCard(
                    title: 'Could not load payments',
                    message: 'Pull down to try again.',
                    icon: Icons.cloud_off_rounded,
                  ),
                  data: (page) => page.items.isEmpty
                      ? const UnavailableCard(
                          title: 'No payments yet',
                          message: 'Payments appear here once a customer pays for a booking.',
                          icon: Icons.history_rounded,
                        )
                      : Column(children: [for (final p in page.items) _PaymentTile(payment: p)]),
                ),
                const SectionHeader('Deductions, net earnings & payouts'),
                UnavailableCard(
                  title: 'Not available yet',
                  message: e.payouts.message.isEmpty
                      ? 'Commission, tax, net earnings and payout status will appear once those rules are approved.'
                      : e.payouts.message,
                  icon: Icons.account_balance_outlined,
                ),
                const SizedBox(height: Gap.md),
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const CircleAvatar(backgroundColor: ZuruvColors.primaryTint, child: Icon(Icons.account_balance_rounded)),
                  title: const Text('Bank & payout settings'),
                  subtitle: const Text('Set up where payouts will go'),
                  trailing: const Icon(Icons.chevron_right_rounded),
                  onTap: () => context.push('/profile/payout'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _PaymentTile extends StatelessWidget {
  const _PaymentTile({required this.payment});

  final OwnerPayment payment;

  @override
  Widget build(BuildContext context) {
    final p = payment;
    final theme = Theme.of(context);
    final when = (p.capturedAt ?? p.createdAt).toLocal();
    return ListTile(
      contentPadding: EdgeInsets.zero,
      onTap: () => context.push('/bookings/${p.bookingId}'),
      title: Text('${p.venueName} · ${p.courtName}'),
      subtitle: Text('${p.bookingCode} · ${when.day}/${when.month}/${when.year}'),
      trailing: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Text(formatMoney(p.amountPaise, currency: p.currency), style: theme.textTheme.titleSmall),
          Text(p.status == 'captured' ? 'Paid' : p.status.replaceAll('_', ' '), style: theme.textTheme.bodySmall),
        ],
      ),
    );
  }
}
