import 'package:flutter/material.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:flutter_shared/testing.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:zuruv/core/storage/preferences.dart';

import 'helpers.dart';

void main() {
  testWidgets('first launch: splash, then onboarding, then login',
      (tester) async {
    final env = TestEnv(gateway: FakeAuthGateway());
    await tester.pumpWidget(await env.app(prefs: {}));
    await tester.pump();
    expect(
        find.text('Discover. Book. Play.'), findsOneWidget); // splash tagline

    await tester.pump(const Duration(milliseconds: 1800));
    await tester.pumpAndSettle();
    expect(find.text('Discover venues\nnear you'), findsOneWidget);

    await tester.tap(find.text('Skip'));
    await tester.pumpAndSettle();
    expect(find.text('Welcome back'), findsOneWidget);
  });

  testWidgets(
      'onboarding: Next x3, Get Started opens registration and is remembered',
      (tester) async {
    final env = TestEnv(gateway: FakeAuthGateway());
    await env.pump(tester, prefs: {});
    for (var i = 0; i < 3; i++) {
      await tester.tap(find.text('Next'));
      await tester.pumpAndSettle();
    }
    expect(find.text('Play, book\nand repeat'), findsOneWidget);
    await tester.tap(find.text('Get Started'));
    await tester.pumpAndSettle();
    expect(find.text('Create account'), findsWidgets);
  });

  testWidgets('returning signed-out user goes straight to login',
      (tester) async {
    await TestEnv(gateway: FakeAuthGateway()).pump(tester);
    expect(find.text('Welcome back'), findsOneWidget);
    expect(find.text('Discover venues\nnear you'), findsNothing);
  });

  testWidgets('protected routes: a signed-out user cannot reach the app',
      (tester) async {
    await TestEnv(gateway: FakeAuthGateway()).pump(tester);
    expect(find.byType(NavigationBar), findsNothing);
  });

  testWidgets(
      'restored customer session lands on Home with the bottom navigation',
      (tester) async {
    await TestEnv().pump(tester);
    expect(find.textContaining('Hi Asha'), findsOneWidget);
    for (final label in [
      'Home',
      'Explore',
      'Bookings',
      'Favorites',
      'Profile'
    ]) {
      expect(inNavBar(label), findsOneWidget);
    }
  });

  testWidgets(
      'a customer lands on the Customer Dashboard, never the owner area',
      (tester) async {
    await TestEnv().pump(tester);
    expect(find.text('Popular venues'), findsOneWidget);
    for (final label in [
      'Home',
      'Explore',
      'Bookings',
      'Favorites',
      'Profile'
    ]) {
      expect(inNavBar(label), findsOneWidget);
    }
    // Typing an owner address (or following an old link) cannot open the owner area.
    final router = GoRouter.of(tester.element(find.byType(NavigationBar)));
    router.go('/owner/dashboard');
    await tester.pumpAndSettle();
    expect(find.text('Popular venues'), findsOneWidget);
    expect(find.text('Dashboard'), findsNothing);
  });

  testWidgets('an admin account is turned away: admins use the website',
      (tester) async {
    await TestEnv(
            gateway:
                FakeAuthGateway(hasSession: true, me: meWith(AppRole.admin)))
        .pump(tester);
    expect(find.byType(NavigationBar), findsNothing);
    expect(find.textContaining('admin website'), findsWidgets);
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
    expect(find.text('No upcoming bookings'), findsOneWidget);

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
