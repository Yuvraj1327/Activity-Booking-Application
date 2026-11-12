import 'package:flutter/material.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:flutter_shared/testing.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:zuruv_customer/core/storage/preferences.dart';

import 'helpers.dart';

void main() {
  testWidgets('first launch: splash, then onboarding, then login', (tester) async {
    final env = TestEnv(gateway: FakeAuthGateway());
    await tester.pumpWidget(await env.app(prefs: {}));
    await tester.pump();
    expect(find.text('Discover. Book. Play.'), findsOneWidget); // splash tagline

    await tester.pump(const Duration(milliseconds: 1800));
    await tester.pumpAndSettle();
    expect(find.text('Discover venues near you'), findsOneWidget);

    await tester.tap(find.text('Skip'));
    await tester.pumpAndSettle();
    expect(find.text('Welcome back'), findsOneWidget);
  });

  testWidgets('onboarding: Next, Next, Get Started opens registration and is remembered', (tester) async {
    final env = TestEnv(gateway: FakeAuthGateway());
    await env.pump(tester, prefs: {});
    await tester.tap(find.text('Next'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Next'));
    await tester.pumpAndSettle();
    expect(find.text('Book in a few taps'), findsOneWidget);
    await tester.tap(find.text('Get Started'));
    await tester.pumpAndSettle();
    expect(find.text('Create account'), findsWidgets);
  });

  testWidgets('returning signed-out user goes straight to login', (tester) async {
    await TestEnv(gateway: FakeAuthGateway()).pump(tester);
    expect(find.text('Welcome back'), findsOneWidget);
    expect(find.text('Discover venues near you'), findsNothing);
  });

  testWidgets('protected routes: a signed-out user cannot reach the app', (tester) async {
    await TestEnv(gateway: FakeAuthGateway()).pump(tester);
    expect(find.byType(NavigationBar), findsNothing);
  });

  testWidgets('restored customer session lands on Home with the bottom navigation', (tester) async {
    await TestEnv().pump(tester);
    expect(find.textContaining('Hi Asha'), findsOneWidget);
    for (final label in ['Home', 'Explore', 'Bookings', 'Favorites', 'Profile']) {
      expect(inNavBar(label), findsOneWidget);
    }
  });

  testWidgets('an owner account is turned away with an explanation', (tester) async {
    await TestEnv(gateway: FakeAuthGateway(hasSession: true, me: meWith(AppRole.owner))).pump(tester);
    expect(find.byType(NavigationBar), findsNothing);
    expect(find.textContaining('owner'), findsWidgets);
  });

  testWidgets('tab state is kept when switching tabs', (tester) async {
    final env = TestEnv();
    await env.pump(tester);
    await tester.tap(inNavBar('Explore'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'ace');
    await tester.pump(const Duration(milliseconds: 600));
    await tester.pumpAndSettle();

    await tester.tap(inNavBar('Bookings'));
    await tester.pumpAndSettle();
    expect(find.text('No bookings yet'), findsOneWidget);

    await tester.tap(inNavBar('Explore'));
    await tester.pumpAndSettle();
    expect(find.text('ace'), findsOneWidget); // the search text survived
  });

  testWidgets('profile: sign out returns to login', (tester) async {
    await TestEnv().pump(tester);
    await tester.tap(inNavBar('Profile'));
    await tester.pumpAndSettle();
    expect(find.text('Asha'), findsOneWidget);
    await tester.ensureVisible(find.text('Sign out'));
    await tester.tap(find.text('Sign out'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(TextButton, 'Sign out'));
    await tester.pumpAndSettle();
    expect(find.text('Welcome back'), findsOneWidget);
  });

  test('onboarding flag key is stable', () {
    expect(PrefKeys.onboardingDone, 'onboarding_done_v1');
  });
}
