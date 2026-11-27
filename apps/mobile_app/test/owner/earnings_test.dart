import 'package:flutter/material.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:zuruv/core/router/app_router.dart';
import 'package:zuruv/owner/shared/models/models.dart';

import 'helpers.dart';

const _na = PendingFeature(dependsOn: 'Business rules not approved', message: 'Not available until rules are approved.');

OwnerEarnings earnings({int gross = 150000, int count = 3, List<VenueGross> venues = const []}) => OwnerEarnings(
      currency: 'INR',
      grossPaidPaise: gross,
      paymentsCount: count,
      byVenue: venues,
      deductions: _na,
      netEarnings: _na,
      payouts: _na,
    );

OwnerPayment payment(String id, {String code = 'ZUR-ABCD2345', int amount = 50000}) => OwnerPayment(
      id: id,
      bookingId: 'b-$id',
      bookingCode: code,
      venueName: 'Ace Arena',
      courtName: 'Court 1',
      amountPaise: amount,
      currency: 'INR',
      status: 'captured',
      createdAt: DateTime.utc(2030, 1, 7),
      capturedAt: DateTime.utc(2030, 1, 7),
    );

void main() {
  Future<void> openEarnings(WidgetTester tester, FakeOwnerRepository repo) async {
    await TestEnv(repo: repo).pump(tester);
    await tester.tap(inNavBar('Earnings'));
    await tester.pumpAndSettle();
  }

  testWidgets('shows the real gross amount and payment records', (tester) async {
    final repo = FakeOwnerRepository()
      ..earningsResult = earnings(venues: const [VenueGross(venueId: 'v1', venueName: 'Ace Arena', grossPaidPaise: 150000, payments: 3)])
      ..paymentList = [payment('p1'), payment('p2', code: 'ZUR-ZZZZ2222')];
    await openEarnings(tester, repo);
    expect(find.text('₹1,500'), findsWidgets);
    expect(find.text('Gross paid by customers'), findsOneWidget);
    expect(find.text('3 paid bookings'), findsOneWidget);
    expect(find.textContaining('ZUR-ABCD2345'), findsOneWidget);
    expect(find.textContaining('ZUR-ZZZZ2222'), findsOneWidget);
  });

  testWidgets('commission, tax, net earnings and payouts are NOT invented', (tester) async {
    await openEarnings(tester, FakeOwnerRepository());
    expect(find.text('Not available yet'), findsOneWidget);
    expect(find.textContaining('not calculated yet'), findsOneWidget);
    expect(find.textContaining('Commission'), findsNothing);
    expect(find.textContaining('GST'), findsNothing);
    expect(find.text('No payments yet'), findsOneWidget);
    expect(find.text('₹0'), findsOneWidget);
  });

  testWidgets('a load failure offers retry', (tester) async {
    final repo = FakeOwnerRepository()..earningsError = const ApiException(statusCode: 0, code: 'NETWORK', message: 'x');
    await openEarnings(tester, repo);
    expect(find.text('Try again'), findsOneWidget);
    repo.earningsError = null;
    await tester.tap(find.text('Try again'));
    await tester.pumpAndSettle();
    expect(find.text('Gross paid by customers'), findsOneWidget);
  });

  testWidgets('shows commission %, deductions and net payable per booking once the backend provides them', (tester) async {
    final repo = FakeOwnerRepository()
      ..earningsResult = earnings(gross: 49560, count: 1)
      ..breakdownResult = EarningsBreakdown.fromJson({
        'available': true,
        'note': 'Net payable is a record, not a transfer.',
        'totals': {'customer_paid_paise': 49560, 'commission_paise': 4000, 'net_payable_paise': 36000, 'net_after_refunds_paise': 36000},
        'items': [
          {
            'booking_id': 'b1', 'booking_code': 'ZUR-ABCD2345', 'venue_name': 'Ace Arena', 'customer_paid_paise': 49560,
            'court_charge_paise': 40000, 'platform_fee_paise': 2000, 'tax_paise': 7560, 'discount_paise': 0,
            'commission_bps': 1000, 'commission_pct': '10%', 'commission_paise': 4000, 'other_deductions_paise': 0,
            'net_payable_paise': 36000, 'refunded_paise': 0, 'net_after_refunds_paise': 36000,
            'formula': '10% of the commission base (40000 paise), rounded half-up to the paisa',
          },
        ],
      });
    await openEarnings(tester, repo);
    expect(find.text('Commission & net earnings'), findsOneWidget);
    expect(find.text('Not available yet'), findsNothing);
    expect(find.textContaining('Commission 10%'), findsOneWidget);
    await tester.scrollUntilVisible(find.textContaining('Ace Arena · ZUR-ABCD2345'), 200, scrollable: find.byType(Scrollable).first);
    await tester.tap(find.textContaining('Ace Arena · ZUR-ABCD2345'));
    await tester.pumpAndSettle();
    expect(find.text('Net payable to you'), findsOneWidget);
    expect(find.textContaining('10% of the commission base'), findsOneWidget);
  });

  test('earnings parse the backend shape and keep unavailable fields unavailable', () {
    final e = OwnerEarnings.fromJson({
      'currency': 'INR',
      'gross_paid_paise': 50000,
      'payments_count': 1,
      'by_venue': [
        {'venue_id': 'v1', 'venue_name': 'Ace', 'gross_paid_paise': 50000, 'payments': 1},
      ],
      'deductions': {'available': false, 'depends_on': 'rules', 'message': 'm'},
      'net_earnings': {'available': false, 'depends_on': 'rules', 'message': 'm'},
      'payouts': {'available': false, 'depends_on': 'rules', 'message': 'm'},
    });
    expect(e.grossPaidPaise, 50000);
    expect(e.byVenue.single.venueName, 'Ace');
    expect(e.payouts.dependsOn, 'rules');
  });

  test('a tapped push opens the related booking, or the notification list', () {
    expect(pushRoute({'booking_id': 'b9'}, AppRole.owner), '/owner/bookings/b9');
    expect(pushRoute({'type': 'payment.received'}, AppRole.owner), '/owner/notifications');
  });
}
