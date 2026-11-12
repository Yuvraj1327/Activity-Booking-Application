import 'package:flutter/material.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:flutter_shared/testing.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:zuruv_owner/core/storage/preferences.dart';

import 'package:zuruv_owner/shared/models/models.dart';

import 'helpers.dart';

void main() {
  testWidgets('first launch: owner splash, five onboarding pages, then registration', (tester) async {
    final env = TestEnv(gateway: FakeAuthGateway());
    tester.view.physicalSize = const Size(900, 1800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(await env.app(prefs: {}));
    await tester.pump();
    expect(find.text('OWNER'), findsOneWidget);
    expect(find.text('Discover. Book. Play.'), findsOneWidget);

    await tester.pump(const Duration(milliseconds: 1800));
    await tester.pumpAndSettle();
    expect(find.text('List your venue'), findsOneWidget);
    for (final title in ['Reach more customers', 'Manage bookings', 'Track earnings', 'Grow your business']) {
      await tester.tap(find.text('Next'));
      await tester.pumpAndSettle();
      expect(find.text(title), findsOneWidget);
    }
    await tester.tap(find.text('Get Started'));
    await tester.pumpAndSettle();
    expect(find.text('Register your business'), findsWidgets);
  });

  testWidgets('returning signed-out owner goes straight to login and cannot reach the app', (tester) async {
    await TestEnv(gateway: FakeAuthGateway()).pump(tester);
    expect(find.text('Welcome back'), findsOneWidget);
    expect(find.byType(NavigationBar), findsNothing);
  });

  testWidgets('restored owner session lands on the dashboard with five tabs', (tester) async {
    await TestEnv().pump(tester);
    expect(find.textContaining('Hello, Asha'), findsOneWidget);
    for (final label in ['Dashboard', 'Venues', 'Bookings', 'Earnings', 'Profile']) {
      expect(inNavBar(label), findsOneWidget);
    }
  });

  testWidgets('a customer account is turned away', (tester) async {
    await TestEnv(gateway: FakeAuthGateway(hasSession: true, me: meWith(AppRole.customer))).pump(tester);
    expect(find.byType(NavigationBar), findsNothing);
    expect(find.textContaining('customer'), findsWidgets);
  });

  testWidgets('onboarding is not shown again once completed', (tester) async {
    await TestEnv(gateway: FakeAuthGateway()).pump(tester, prefs: {PrefKeys.onboardingDone: true});
    expect(find.text('List your venue'), findsNothing);
  });

  testWidgets('dashboard shows real booking counts and marks revenue and utilization unavailable', (tester) async {
    await TestEnv().pump(tester);
    expect(find.text('4.6'), findsOneWidget); // average rating from the API
    expect(find.text('Published'), findsWidgets);
    expect(find.text('Total revenue'), findsOneWidget);
    expect(find.text('Available with payments'), findsOneWidget);
    expect(find.text('Total bookings'), findsOneWidget);
    expect(find.text('Upcoming'), findsOneWidget); // booking overview comes from the API
    expect(find.text('Completed'), findsOneWidget);
    expect(find.text('Available with online booking'), findsOneWidget); // utilization is still unavailable
    expect(find.textContaining('₹0'), findsNothing); // never a fake zero
  });

  testWidgets('dashboard with no venues invites the owner to add one', (tester) async {
    final repo = FakeOwnerRepository(venues: []);
    await TestEnv(repo: repo).pump(tester);
    expect(find.text('Add your first venue'), findsOneWidget);
  });

  testWidgets('dashboard error offers a retry', (tester) async {
    final failing = _FailingDashboardRepo();
    await TestEnv(repo: failing).pump(tester);
    expect(find.text('Try again'), findsOneWidget);
  });

  testWidgets('bookings tab shows real bookings, earnings shows only confirmed facts', (tester) async {
    final repo = FakeOwnerRepository()
      ..bookingList = [bookingOf('b1'), bookingOf('b2', status: 'completed', customer: 'Old Customer')];
    await TestEnv(repo: repo).pump(tester);
    await tester.tap(inNavBar('Bookings'));
    await tester.pumpAndSettle();
    expect(find.text('Cathy Customer'), findsOneWidget);
    expect(find.text('ZUR-ABCD2345 · ₹500'), findsOneWidget);
    expect(find.text('Old Customer'), findsNothing);
    await tester.tap(find.text('Past'));
    await tester.pumpAndSettle();
    expect(find.text('Old Customer'), findsOneWidget);
    await tester.tap(find.text('Cancelled'));
    await tester.pumpAndSettle();
    expect(find.text('No cancelled bookings yet'), findsOneWidget);

    await tester.tap(inNavBar('Earnings'));
    await tester.pumpAndSettle();
    expect(find.text('Payments & Earnings'), findsOneWidget);
    expect(find.text('No payments yet'), findsOneWidget);
  });

  testWidgets('booking details are read-only: customer name, court, history, no status buttons', (tester) async {
    final repo = FakeOwnerRepository()..bookingList = [bookingOf('b1')];
    await TestEnv(repo: repo).pump(tester);
    await tester.tap(inNavBar('Bookings'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Cathy Customer'));
    await tester.pumpAndSettle();
    expect(find.text('Booking ZUR-ABCD2345'), findsOneWidget);
    expect(find.text('Court 1'), findsOneWidget);
    expect(find.text('History'), findsOneWidget);
    expect(find.text('Not paid'), findsOneWidget);
    expect(find.byType(FilledButton), findsNothing);
    expect(find.textContaining('Cancel'), findsNothing);
  });

  testWidgets('bookings load failure offers retry', (tester) async {
    final repo = FakeOwnerRepository()..bookingsError = const ApiException(statusCode: 0, code: 'NETWORK', message: 'x');
    await TestEnv(repo: repo).pump(tester);
    await tester.tap(inNavBar('Bookings'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Cannot reach the server'), findsOneWidget);
    repo
      ..bookingsError = null
      ..bookingList = [bookingOf('b1')];
    await tester.tap(find.text('Try again'));
    await tester.pumpAndSettle();
    expect(find.text('Cathy Customer'), findsOneWidget);
  });

  testWidgets('notifications: unread first, tap marks read, filter by group', (tester) async {
    final repo = FakeOwnerRepository();
    await TestEnv(repo: repo).pump(tester);
    await tester.tap(find.byIcon(Icons.notifications_none_rounded));
    await tester.pumpAndSettle();
    expect(find.text('New booking'), findsOneWidget);
    expect(find.text('New review'), findsOneWidget);

    await tester.tap(find.text('New booking'));
    await tester.pumpAndSettle();
    expect(repo.markedRead, ['n1']);

    await tester.tap(find.text('Reviews'));
    await tester.pumpAndSettle();
    expect(find.text('New booking'), findsNothing);
    expect(find.text('New review'), findsOneWidget);
  });

  testWidgets('profile: menu, business info save, preferences and logout', (tester) async {
    final repo = FakeOwnerRepository();
    final env = TestEnv(repo: repo);
    await env.pump(tester);
    await tester.tap(inNavBar('Profile'));
    await tester.pumpAndSettle();
    expect(find.text('Ace Sports'), findsOneWidget);

    await tester.tap(find.text('Business information'));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextFormField, 'Business name'), 'Ace Sports Pvt');
    await tester.tap(find.text('Save changes'));
    await tester.pumpAndSettle();
    expect(repo.businessUpdates.single, {'business_name': 'Ace Sports Pvt'});

    await tester.tap(find.text('Bank & payout settings'));
    await tester.pumpAndSettle();
    expect(find.text('Not available yet'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, 'Save bank details'), findsNothing); // nothing is collected
    expect(find.byType(TextField), findsNothing);
    await tester.pageBack();
    await tester.pumpAndSettle();

    await tester.tap(find.text('Notification preferences'));
    await tester.pumpAndSettle();
    expect(find.text('Push notifications'), findsOneWidget);
    await tester.tap(find.widgetWithText(SwitchListTile, 'Push notifications'));
    await tester.pumpAndSettle();
    expect(repo.channelUpdates.single, {'push': false, 'email': null}); // stored through the API
    await tester.pageBack();
    await tester.pumpAndSettle();

    await tester.tap(find.text('Log out'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(TextButton, 'Log out'));
    await tester.pumpAndSettle();
    expect(find.text('Welcome back'), findsOneWidget);
  });

  testWidgets('analytics: date filter, unavailable metrics are labelled', (tester) async {
    await TestEnv().pump(tester);
    await tester.tap(inNavBar('Profile'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Analytics'));
    await tester.pumpAndSettle();
    expect(find.text('7 days'), findsOneWidget);
    expect(find.text('Total bookings'), findsOneWidget);
    await tester.tap(find.text('7 days'));
    await tester.pumpAndSettle();
    expect(find.text('Revenue'), findsOneWidget);
  });

  testWidgets('reviews: empty state when there are none', (tester) async {
    await TestEnv().pump(tester);
    await tester.tap(inNavBar('Profile'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Reviews'));
    await tester.pumpAndSettle();
    expect(find.text('No reviews yet'), findsOneWidget);
  });

  testWidgets('reviews: summary, star filter and a single reply', (tester) async {
    final repo = FakeOwnerRepository()
      ..reviewList = [
        OwnerReview(
          id: 'r1', rating: 5, comment: 'Superb court', reviewerName: 'Priya S.', venueName: 'Ace Arena',
          bookingCode: 'ZUR-1', createdAt: DateTime(2030, 1, 1), replyBody: null, replyAt: null,
        ),
        OwnerReview(
          id: 'r2', rating: 3, comment: null, reviewerName: 'Rahul V.', venueName: 'Ace Arena',
          bookingCode: 'ZUR-2', createdAt: DateTime(2030, 1, 1), replyBody: null, replyAt: null,
        ),
      ];
    await TestEnv(repo: repo).pump(tester);
    await tester.tap(inNavBar('Profile'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Reviews'));
    await tester.pumpAndSettle();
    expect(find.textContaining('4.0 average from 2 reviews'), findsOneWidget);
    expect(find.text('Priya S.'), findsOneWidget);

    await tester.tap(find.textContaining('3\u2605'));
    await tester.pumpAndSettle();
    expect(find.text('Priya S.'), findsNothing);
    expect(find.text('Rahul V.'), findsOneWidget);

    await tester.tap(find.text('Reply'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'Thanks for playing');
    await tester.tap(find.text('Post reply'));
    await tester.pumpAndSettle();
    expect(repo.replies, ['r2:Thanks for playing']);
    expect(find.text('Your reply'), findsOneWidget);
    expect(find.text('Reply'), findsNothing); // one reply per review
  });
}

class _FailingDashboardRepo extends FakeOwnerRepository {
  @override
  Future<Dashboard> dashboard() async => throw const ApiException(statusCode: 500, code: 'X', message: 'Something broke.');
}
