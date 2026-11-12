import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:flutter_shared/testing.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:zuruv_owner/app.dart';
import 'package:zuruv_owner/core/providers.dart';

Widget appWith(FakeAuthGateway gateway) => ProviderScope(
      overrides: [
        authGatewayProvider.overrideWithValue(gateway),
        expectedRoleProvider.overrideWithValue(AppRole.owner),
        authUiConfigProvider.overrideWithValue(const AuthUiConfig(appName: 'ZURUV Owner', role: AppRole.owner)),
        backendHealthProvider.overrideWith((ref) async => {
              'status': 'degraded',
              'database': {'status': 'not_configured'},
            }),
      ],
      child: const ZuruvOwnerApp(),
    );

MeResponse meWith(AppRole role) => MeResponse(
      userId: 'u1',
      hasProfile: true,
      profile: UserProfile(id: 'u1', role: role, status: 'active', fullName: 'Asha'),
    );

void main() {
  testWidgets('signed-out user sees the login screen', (tester) async {
    await tester.pumpWidget(appWith(FakeAuthGateway()));
    await tester.pumpAndSettle();
    expect(find.text('Welcome back'), findsOneWidget);
    expect(find.text('Sign in'), findsOneWidget);
    expect(find.text('Create account'), findsOneWidget);
  });

  testWidgets('restored owner session lands on the home screen and can sign out', (tester) async {
    final gateway = FakeAuthGateway(hasSession: true, me: meWith(AppRole.owner));
    await tester.pumpWidget(appWith(gateway));
    await tester.pumpAndSettle();
    expect(find.textContaining('Hello, Asha'), findsOneWidget);

    await tester.tap(find.byTooltip('Sign out'));
    await tester.pumpAndSettle();
    expect(find.text('Welcome back'), findsOneWidget);
  });

  testWidgets('a customer account is turned away with an explanation', (tester) async {
    await tester.pumpWidget(appWith(FakeAuthGateway(hasSession: true, me: meWith(AppRole.customer))));
    await tester.pumpAndSettle();
    expect(find.text('Welcome back'), findsOneWidget);
    expect(find.textContaining('account'), findsWidgets);
    expect(find.textContaining('Hello, Asha'), findsNothing);
  });

  testWidgets('login form validates input before calling the server', (tester) async {
    final gateway = FakeAuthGateway();
    await tester.pumpWidget(appWith(gateway));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Sign in'));
    await tester.pump();
    expect(find.text('Enter your e-mail'), findsOneWidget);
    expect(gateway.calls, isNot(contains('signIn')));
  });
}
