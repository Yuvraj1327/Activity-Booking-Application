import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:go_router/go_router.dart';

import 'package:zuruv/core/constants/tokens.dart';
import 'package:zuruv/owner/core/utils/format.dart';
import 'package:zuruv/owner/shared/models/models.dart';
import 'package:zuruv/owner/shared/repositories/owner_repository.dart';
import 'package:zuruv/owner/shared/widgets/common_widgets.dart';

final earningsProvider = FutureProvider.autoDispose<OwnerEarnings>((ref) => ref.watch(ownerRepositoryProvider).earnings());
/// Commission and net payable per booking. If it cannot be loaded the screen simply keeps showing the
/// "not available" card: nothing is ever estimated on the phone.
final earningsBreakdownProvider = FutureProvider.autoDispose<EarningsBreakdown>((ref) async {
  try {
    return await ref.watch(ownerRepositoryProvider).earningsBreakdown();
  } catch (_) {
    return const EarningsBreakdown(available: false);
  }
});
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
    final breakdown = ref.watch(earningsBreakdownProvider).valueOrNull;
    return Scaffold(
      appBar: AppBar(title: const Text('Payments & Earnings'), titleSpacing: Gap.page),
      body: data.when(
        loading: () => const LoadingView(),
        error: (e, _) => ErrorView.fromError(e, onRetry: () {
          ref.invalidate(earningsProvider);
          ref.invalidate(ownerPaymentsProvider);
          ref.invalidate(earningsBreakdownProvider);
        }),
        data: (e) => ResponsivePage(
          maxWidth: 720,
          child: RefreshIndicator(
            onRefresh: () async {
              ref.invalidate(earningsProvider);
              ref.invalidate(ownerPaymentsProvider);
              ref.invalidate(earningsBreakdownProvider);
            },
            child: ListView(
              padding: const EdgeInsets.only(top: 4, bottom: 32),
              children: [
                HeroStatCard(
                  label: 'Gross paid by customers',
                  icon: Icons.account_balance_wallet_rounded,
                  value: formatMoney(e.grossPaidPaise, currency: e.currency),
                ),
                const SizedBox(height: Gap.md),
                IntrinsicHeight(
                  child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                    Expanded(child: StatTile(label: 'Paid bookings', icon: Icons.receipt_long_rounded, value: '${e.paymentsCount}')),
                    const SizedBox(width: Gap.md),
                    Expanded(
                      child: StatTile(
                        label: 'Average per booking',
                        icon: Icons.trending_up_rounded,
                        value: e.paymentsCount == 0 ? null : formatMoney((e.grossPaidPaise / e.paymentsCount).round(), currency: e.currency),
                        note: e.paymentsCount == 0 ? 'No paid bookings yet' : null,
                      ),
                    ),
                  ]),
                ),
                const SizedBox(height: Gap.sm),
                Text(
                  'Gross amounts only. Platform fees, tax and net earnings are not calculated yet.',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(color: ZuruvColors.textSecondary),
                ),
                if (e.byVenue.isNotEmpty) ...[
                  const SectionHeader('By venue'),
                  for (final v in e.byVenue)
                    Padding(
                      padding: const EdgeInsets.only(bottom: Gap.sm),
                      child: OwnerCard(
                        padding: const EdgeInsets.symmetric(horizontal: Gap.lg, vertical: Gap.md),
                        child: Row(children: [
                          const IconBadge(Icons.storefront_rounded, size: 38),
                          const SizedBox(width: Gap.md),
                          Expanded(
                            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                              Text(v.venueName, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w700)),
                              Text('${v.payments} paid booking${v.payments == 1 ? '' : 's'}', style: Theme.of(context).textTheme.bodySmall?.copyWith(color: ZuruvColors.textSecondary)),
                            ]),
                          ),
                          Text(formatMoney(v.grossPaidPaise, currency: e.currency), style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w800)),
                        ]),
                      ),
                    ),
                ],
                const SectionHeader('Payment history'),
                payments.when(
                  loading: () => const Padding(padding: EdgeInsets.all(Gap.lg), child: Center(child: CircularProgressIndicator())),
                  error: (err, _) => const UnavailableCard(
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
                if (breakdown != null && breakdown.available) ...[
                  const SectionHeader('Commission & net earnings'),
                  _BreakdownSummary(b: breakdown, currency: e.currency),
                  const SizedBox(height: Gap.sm),
                  for (final i in breakdown.items) _EarningTile(item: i, currency: e.currency),
                  if (breakdown.note.isNotEmpty)
                    Text(breakdown.note, style: Theme.of(context).textTheme.bodySmall?.copyWith(color: ZuruvColors.textSecondary)),
                ] else ...[
                const SectionHeader('Deductions, net earnings & payouts'),
                UnavailableCard(
                  title: 'Not available yet',
                  message: e.payouts.message.isEmpty
                      ? 'Commission, tax, net earnings and payout status will appear once those rules are approved.'
                      : e.payouts.message,
                  icon: Icons.account_balance_outlined,
                ),
                ],
                const SizedBox(height: Gap.md),
                OwnerCard(
                  padding: const EdgeInsets.symmetric(horizontal: Gap.lg, vertical: Gap.md),
                  onTap: () => context.push('/owner/profile/payout'),
                  child: Row(children: [
                    const IconBadge(Icons.account_balance_rounded, size: 40),
                    const SizedBox(width: Gap.md),
                    Expanded(
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        const Text('Bank & payout settings', style: TextStyle(fontWeight: FontWeight.w700)),
                        Text('Set up where payouts will go', style: Theme.of(context).textTheme.bodySmall?.copyWith(color: ZuruvColors.textSecondary)),
                      ]),
                    ),
                    const Icon(Icons.chevron_right_rounded, color: ZuruvColors.textSecondary),
                  ]),
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
    final paid = p.status == 'captured';
    return Padding(
      padding: const EdgeInsets.only(bottom: Gap.sm),
      child: OwnerCard(
        padding: const EdgeInsets.symmetric(horizontal: Gap.lg, vertical: Gap.md),
        onTap: () => context.push('/owner/bookings/${p.bookingId}'),
        child: Row(children: [
          IconBadge(paid ? Icons.check_circle_outline_rounded : Icons.history_rounded, size: 40, color: paid ? ZuruvColors.success : ZuruvColors.textSecondary),
          const SizedBox(width: Gap.md),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('${p.venueName} · ${p.courtName}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w700)),
              const SizedBox(height: 2),
              Text('${p.bookingCode} · ${when.day}/${when.month}/${when.year}', maxLines: 1, overflow: TextOverflow.ellipsis, style: theme.textTheme.bodySmall?.copyWith(color: ZuruvColors.textSecondary)),
            ]),
          ),
          const SizedBox(width: Gap.sm),
          Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(formatMoney(p.amountPaise, currency: p.currency), style: theme.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w800)),
              Text(paid ? 'Paid' : p.status.replaceAll('_', ' '), style: theme.textTheme.bodySmall?.copyWith(color: paid ? ZuruvColors.success : ZuruvColors.textSecondary, fontWeight: FontWeight.w600)),
            ],
          ),
        ]),
      ),
    );
  }
}

class _BreakdownSummary extends StatelessWidget {
  const _BreakdownSummary({required this.b, required this.currency});

  final EarningsBreakdown b;
  final String currency;

  @override
  Widget build(BuildContext context) {
    return Column(children: [
      HeroStatCard(label: 'Net earnings after commission', icon: Icons.savings_rounded, value: formatMoney(b.netAfterRefundsPaise, currency: currency)),
      const SizedBox(height: Gap.md),
      IntrinsicHeight(
        child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Expanded(child: StatTile(label: 'Platform commission', icon: Icons.percent_rounded, value: formatMoney(b.commissionPaise, currency: currency))),
          const SizedBox(width: Gap.md),
          Expanded(child: StatTile(label: 'Paid by customers', icon: Icons.payments_rounded, value: formatMoney(b.customerPaidPaise, currency: currency))),
        ]),
      ),
    ]);
  }
}

class _EarningTile extends StatelessWidget {
  const _EarningTile({required this.item, required this.currency});

  final EarningItem item;
  final String currency;

  Widget _row(BuildContext context, String label, int paise, {bool bold = false, bool minus = false}) {
    final style = Theme.of(context).textTheme.bodyMedium?.copyWith(fontWeight: bold ? FontWeight.w800 : FontWeight.w500);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        Flexible(child: Text(label, style: style?.copyWith(color: bold ? null : ZuruvColors.textSecondary))),
        Text('${minus ? '− ' : ''}${formatMoney(paise, currency: currency)}', style: style),
      ]),
    );
  }

  @override
  Widget build(BuildContext context) {
    final i = item;
    return Padding(
      padding: const EdgeInsets.only(bottom: Gap.sm),
      child: OwnerCard(
        padding: const EdgeInsets.symmetric(horizontal: Gap.lg, vertical: Gap.md),
        child: Theme(
          data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
          child: ExpansionTile(
            tilePadding: EdgeInsets.zero,
            childrenPadding: EdgeInsets.zero,
            title: Text('${i.venueName} · ${i.bookingCode}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w700)),
            subtitle: Text('Commission ${i.commissionPct ?? '—'} · Net ${formatMoney(i.netPayablePaise, currency: currency)}'),
            children: [
              _row(context, 'Customer paid', i.customerPaidPaise),
              _row(context, 'Court charge', i.courtChargePaise),
              if (i.platformFeePaise > 0) _row(context, 'Platform fee (paid by customer)', i.platformFeePaise),
              if (i.taxPaise > 0) _row(context, 'Tax (collected, not yours)', i.taxPaise),
              _row(context, 'Commission ${i.commissionPct ?? ''}'.trim(), i.commissionPaise, minus: true),
              if (i.otherDeductionsPaise != 0) _row(context, 'Other deductions', i.otherDeductionsPaise, minus: true),
              const Divider(height: Gap.md),
              _row(context, 'Net payable to you', i.netPayablePaise, bold: true),
              if (i.refundedPaise > 0) _row(context, 'After refunds (${formatMoney(i.refundedPaise, currency: currency)} refunded)', i.netAfterRefundsPaise),
              const SizedBox(height: Gap.xs),
              Text(i.formula, style: Theme.of(context).textTheme.bodySmall?.copyWith(color: ZuruvColors.textSecondary)),
            ],
          ),
        ),
      ),
    );
  }
}
