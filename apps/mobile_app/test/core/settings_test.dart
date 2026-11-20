import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:zuruv/core/storage/preferences.dart';

import '../customer/helpers.dart' as c;
import '../owner/helpers.dart' as o;

Future<void> openSettings(WidgetTester tester, {required bool owner}) async {
  await tester.tap(owner ? o.inNavBar('Profile') : c.inNavBar('Profile'));
  await tester.pumpAndSettle();
  await tester.tap(find.text('Settings'));
  await tester.pumpAndSettle();
}

Future<void> openRow(WidgetTester tester, String title) async {
  await tester.tap(find.text(title));
  await tester.pumpAndSettle();
}

void main() {
  setUp(() => PackageInfo.setMockInitialValues(
        appName: 'ZURUV', packageName: 'app.zuruv', version: '1.2.3', buildNumber: '45', buildSignature: ''));

  group('Customer settings', () {
    testWidgets('hub lists every section', (tester) async {
      final env = c.TestEnv();
      await env.pump(tester);
      await openSettings(tester, owner: false);
      for (final t in ['Profile', 'Account', 'Appearance', 'Preferences', 'Notifications', 'Privacy & security', 'Help & support', 'About']) {
        expect(find.text(t), findsWidgets, reason: t);
      }
      expect(find.text('Player'), findsOneWidget);
    });

    testWidgets('appearance: dark theme applies and is remembered', (tester) async {
      final env = c.TestEnv();
      await env.pump(tester);
      await openSettings(tester, owner: false);
      await openRow(tester, 'Appearance');
      await tester.tap(find.text('Dark'));
      await tester.pumpAndSettle();
      expect(Theme.of(tester.element(find.byType(Scaffold).last)).brightness, Brightness.dark);
      // restart: a fresh app reads the stored choice
      final env2 = c.TestEnv();
      await tester.pumpWidget(await env2.app(prefs: {PrefKeys.onboardingDone: true, 'theme_mode_v1': 'dark'}));
      await tester.pump(const Duration(seconds: 4));
      await tester.pumpAndSettle();
      expect(Theme.of(tester.element(find.byType(Scaffold).first)).brightness, Brightness.dark);
    });

    testWidgets('notifications: every switch is stored through the API', (tester) async {
      final env = c.TestEnv();
      await env.pump(tester);
      await openSettings(tester, owner: false);
      await openRow(tester, 'Notifications');
      for (final t in ['Push notifications', 'E-mail', 'Bookings', 'Payments', 'Offers & promotions']) {
        await tester.tap(find.widgetWithText(SwitchListTile, t));
        await tester.pumpAndSettle();
      }
      expect(env.settings.prefUpdates, [
        {'push_enabled': false},
        {'email_enabled': false},
        {'booking_enabled': false},
        {'payment_enabled': false},
        {'promo_enabled': false},
      ]);
      expect(tester.widget<SwitchListTile>(find.widgetWithText(SwitchListTile, 'Bookings')).value, isFalse);
    });

    testWidgets('notifications: a failed save shows an error and keeps the old value', (tester) async {
      final env = c.TestEnv();
      await env.pump(tester);
      await openSettings(tester, owner: false);
      await openRow(tester, 'Notifications');
      env.settings.failNext = true;
      await tester.tap(find.widgetWithText(SwitchListTile, 'Payments'));
      await tester.pumpAndSettle();
      expect(find.text('Server said no.'), findsOneWidget);
      expect(tester.widget<SwitchListTile>(find.widgetWithText(SwitchListTile, 'Payments')).value, isTrue);
    });

    testWidgets('preferences: sports interests and language', (tester) async {
      final env = c.TestEnv();
      await env.pump(tester);
      await openSettings(tester, owner: false);
      await openRow(tester, 'Preferences');
      await tester.tap(find.widgetWithText(FilterChip, 'Badminton'));
      await tester.pumpAndSettle();
      expect(env.settings.interestIds, ['k1']);
      await tester.tap(find.widgetWithText(FilterChip, 'Tennis'));
      await tester.pumpAndSettle();
      expect(env.settings.interestIds, ['k1', 'k2']);
      await tester.tap(find.widgetWithText(FilterChip, 'Badminton'));
      await tester.pumpAndSettle();
      expect(env.settings.interestIds, ['k2']);
      expect(find.text('City'), findsOneWidget);

      await tester.tap(find.text('हिन्दी (Hindi)'));
      await tester.pumpAndSettle();
      expect(env.settings.languages, ['hi']);
      expect(Localizations.localeOf(tester.element(find.byType(Scaffold).last)).languageCode, 'hi');
    });

    testWidgets('account: password validation, change, and deletion request / cancel', (tester) async {
      final env = c.TestEnv();
      await env.pump(tester);
      await openSettings(tester, owner: false);
      await openRow(tester, 'Account');
      expect(find.text('asha@example.com'), findsOneWidget);

      Future<void> fill(String cur, String nw, String conf) async {
        await tester.enterText(find.widgetWithText(TextFormField, 'Current password'), cur);
        await tester.enterText(find.widgetWithText(TextFormField, 'New password'), nw);
        await tester.enterText(find.widgetWithText(TextFormField, 'Confirm new password'), conf);
      }

      await tester.ensureVisible(find.text('Update password'));
      await fill('oldpass123', 'short', 'short');
      await tester.tap(find.text('Update password'));
      await tester.pumpAndSettle();
      expect(find.text('Use at least 8 characters'), findsOneWidget);
      await fill('oldpass123', 'newpass1234', 'different123');
      await tester.tap(find.text('Update password'));
      await tester.pumpAndSettle();
      expect(find.text('Passwords don\'t match'), findsOneWidget);
      expect(env.gateway.calls, isNot(contains('updatePassword')));

      await fill('oldpass123', 'newpass1234', 'newpass1234');
      await tester.tap(find.text('Update password'));
      await tester.pumpAndSettle();
      expect(env.gateway.calls, containsAllInOrder(['signIn', 'updatePassword'])); // verified, then changed
      expect(find.text('Password changed'), findsOneWidget);

      await tester.ensureVisible(find.text('Request account deletion'));
      await tester.tap(find.text('Request account deletion'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Send request'));
      await tester.pumpAndSettle();
      expect(env.settings.deletionRequests, 1);
      expect(find.textContaining('Deletion requested on'), findsOneWidget);
      await tester.tap(find.text('Cancel deletion request'));
      await tester.pumpAndSettle();
      expect(env.settings.deletionCancels, 1);
      expect(find.text('Request account deletion'), findsOneWidget);
    });

    testWidgets('privacy: sign out of all devices', (tester) async {
      final env = c.TestEnv();
      await env.pump(tester);
      await openSettings(tester, owner: false);
      await openRow(tester, 'Privacy & security');
      expect(find.textContaining('this device'), findsWidgets);
      await tester.tap(find.text('Sign out of all devices'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(TextButton, 'Sign out'));
      await tester.pumpAndSettle();
      expect(env.gateway.calls, contains('signOutEverywhere'));
      expect(find.text('Welcome back'), findsOneWidget);
    });

    testWidgets('help: faq, validation, send feedback, history, about version', (tester) async {
      final env = c.TestEnv();
      await env.pump(tester);
      await openSettings(tester, owner: false);
      await openRow(tester, 'Help & support');
      await tester.tap(find.text('How do I book a venue?'));
      await tester.pumpAndSettle();
      expect(find.textContaining('choose a sport'), findsOneWidget);

      await openRow(tester, 'Report an issue');
      await tester.tap(find.text('Send'));
      await tester.pumpAndSettle();
      expect(find.text('Enter at least 3 characters'), findsOneWidget);
      await tester.enterText(find.widgetWithText(TextFormField, 'What went wrong?'), 'Slots missing');
      await tester.enterText(find.widgetWithText(TextFormField, 'Details'), 'The 7 PM slot never shows up.');
      await tester.tap(find.text('Send'));
      await tester.pumpAndSettle();
      expect(env.settings.sent.single['kind'], 'issue');
      expect(find.textContaining('Thanks for the report'), findsOneWidget);
      await tester.tap(find.text('Done'));
      await tester.pumpAndSettle();

      await openRow(tester, 'My messages');
      expect(find.text('Slots missing'), findsOneWidget);
      GoRouter.of(tester.element(find.byType(Scaffold).last)).go('/settings/about');
      await tester.pumpAndSettle();
      expect(find.text('Version 1.2.3 (45)'), findsOneWidget);
      await openRow(tester, 'Privacy Policy');
      expect(find.textContaining('pending legal review'), findsOneWidget);
    });
  });

  group('Owner settings', () {
    testWidgets('hub, no sports section, own notification + help content', (tester) async {
      final env = o.TestEnv();
      await env.pump(tester);
      await openSettings(tester, owner: true);
      expect(find.text('Venue owner'), findsOneWidget);
      await openRow(tester, 'Preferences');
      expect(find.byType(FilterChip), findsNothing);
      expect(find.text('English'), findsOneWidget);
      await tester.pageBack();
      await tester.pumpAndSettle();

      await openRow(tester, 'Notifications');
      await tester.tap(find.widgetWithText(SwitchListTile, 'Payments'));
      await tester.pumpAndSettle();
      expect(env.settings.prefUpdates.single, {'payment_enabled': false});
      await tester.pageBack();
      await tester.pumpAndSettle();

      await openRow(tester, 'Help & support');
      expect(find.text('When does my venue go live?'), findsOneWidget);
      expect(find.text('How do I book a venue?'), findsNothing);
      await openRow(tester, 'Send feedback');
      await tester.enterText(find.widgetWithText(TextFormField, 'Title'), 'Great app');
      await tester.enterText(find.widgetWithText(TextFormField, 'Your feedback'), 'Please add a calendar view.');
      await tester.tap(find.text('Send'));
      await tester.pumpAndSettle();
      expect(env.settings.sent.single['kind'], 'feedback');
    });

    testWidgets('account deletion request works for owners too', (tester) async {
      final env = o.TestEnv();
      await env.pump(tester);
      await openSettings(tester, owner: true);
      await openRow(tester, 'Account');
      await tester.ensureVisible(find.text('Request account deletion'));
      await tester.tap(find.text('Request account deletion'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Send request'));
      await tester.pumpAndSettle();
      expect(env.settings.deletionRequests, 1);
    });

    testWidgets('dark theme works in the owner theme', (tester) async {
      final env = o.TestEnv();
      await env.pump(tester);
      await openSettings(tester, owner: true);
      await openRow(tester, 'Appearance');
      await tester.tap(find.text('Dark'));
      await tester.pumpAndSettle();
      expect(Theme.of(tester.element(find.byType(Scaffold).last)).brightness, Brightness.dark);
    });
  });
}
