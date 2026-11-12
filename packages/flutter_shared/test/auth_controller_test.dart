import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:flutter_shared/testing.dart';
import 'package:flutter_test/flutter_test.dart';

ProviderContainer containerFor(FakeAuthGateway gateway, AppRole role) {
  final c = ProviderContainer(overrides: [
    authGatewayProvider.overrideWithValue(gateway),
    expectedRoleProvider.overrideWithValue(role),
  ]);
  addTearDown(c.dispose);
  return c;
}

MeResponse meWith(AppRole role, {String status = 'active'}) => MeResponse(
      userId: 'u1',
      hasProfile: true,
      profile: UserProfile(id: 'u1', role: role, status: status, fullName: 'Asha'),
    );

Future<void> settle() => Future<void>.delayed(const Duration(milliseconds: 20));

void main() {
  test('no stored session -> unauthenticated, API never called', () {
    final g = FakeAuthGateway();
    final c = containerFor(g, AppRole.customer);
    expect(c.read(authControllerProvider), isA<Unauthenticated>());
    expect(g.calls, isEmpty);
  });

  test('stored session is restored and confirmed with the API', () async {
    final g = FakeAuthGateway(hasSession: true, me: meWith(AppRole.customer));
    final c = containerFor(g, AppRole.customer);
    expect(c.read(authControllerProvider), isA<AuthInitializing>());
    await settle();
    final s = c.read(authControllerProvider);
    expect(s, isA<Authenticated>());
    expect((s as Authenticated).profile.fullName, 'Asha');
  });

  test('wrong role is signed out with an explanation', () async {
    final g = FakeAuthGateway(hasSession: true, me: meWith(AppRole.owner));
    final c = containerFor(g, AppRole.customer);
    await settle();
    final s = c.read(authControllerProvider);
    expect(s, isA<Unauthenticated>());
    expect((s as Unauthenticated).notice, contains('venue owner'));
    expect(g.calls, contains('signOut'));
  });

  test('suspended account is blocked', () async {
    final g = FakeAuthGateway(hasSession: true, me: meWith(AppRole.customer, status: 'suspended'));
    final c = containerFor(g, AppRole.customer);
    await settle();
    expect(c.read(authControllerProvider), isA<AccountSuspended>());
  });

  test('401 from the API signs the user out', () async {
    final g = FakeAuthGateway(
      hasSession: true,
      meError: const ApiException(statusCode: 401, code: 'TOKEN_EXPIRED', message: 'expired'),
    );
    final c = containerFor(g, AppRole.customer);
    await settle();
    expect(c.read(authControllerProvider), isA<Unauthenticated>());
    expect(g.calls, contains('signOut'));
  });

  test('network failure keeps the session and shows a retryable error', () async {
    final g = FakeAuthGateway(
      hasSession: true,
      meError: const ApiException(statusCode: 0, code: 'NETWORK_ERROR', message: 'offline'),
    );
    final c = containerFor(g, AppRole.customer);
    await settle();
    expect(c.read(authControllerProvider), isA<AuthFailure>());
    expect(g.calls, isNot(contains('signOut')));
  });

  test('registered through the app: profile is created automatically from sign-up details', () async {
    final g = FakeAuthGateway(
      hasSession: true,
      metadata: {'full_name': 'Ravi', 'business_name': 'Ravi Arena'},
      me: const MeResponse(userId: 'u1', hasProfile: false),
    );
    final c = containerFor(g, AppRole.owner);
    await settle();
    expect(c.read(authControllerProvider), isA<Authenticated>());
    expect(g.lastCreateRequest?.role, AppRole.owner);
    expect(g.lastCreateRequest?.businessName, 'Ravi Arena');
  });

  test('no details available -> asks for them (NeedsProfile)', () async {
    final g = FakeAuthGateway(hasSession: true, me: const MeResponse(userId: 'u1', hasProfile: false));
    final c = containerFor(g, AppRole.customer);
    await settle();
    expect(c.read(authControllerProvider), isA<NeedsProfile>());
    await c.read(authControllerProvider.notifier).completeProfile(fullName: 'Asha');
    expect(c.read(authControllerProvider), isA<Authenticated>());
    expect(g.lastCreateRequest?.role, AppRole.customer); // role comes from the app, never the form
  });

  test('sign in then sign out', () async {
    final g = FakeAuthGateway(me: meWith(AppRole.customer));
    final c = containerFor(g, AppRole.customer);
    final controller = c.read(authControllerProvider.notifier);
    await controller.signIn('a@b.co', 'secret123');
    await settle();
    expect(c.read(authControllerProvider), isA<Authenticated>());
    await controller.signOut();
    expect(c.read(authControllerProvider), isA<Unauthenticated>());
  });

  test('password recovery event routes to the reset screen state', () async {
    final g = FakeAuthGateway();
    final c = containerFor(g, AppRole.customer);
    c.read(authControllerProvider);
    g.emit(GatewayEvent.passwordRecovery);
    await settle();
    expect(c.read(authControllerProvider), isA<PasswordRecovery>());
  });

  group('authRedirect', () {
    test('signed-out users can only see public pages', () {
      expect(authRedirect(const Unauthenticated(), '/'), '/login');
      expect(authRedirect(const Unauthenticated(), '/bookings'), '/login');
      expect(authRedirect(const Unauthenticated(), '/login'), isNull);
      expect(authRedirect(const Unauthenticated(), '/register'), isNull);
      // App-specific public pages (e.g. onboarding) are opt-in.
      expect(authRedirect(const Unauthenticated(), '/onboarding'), '/login');
      expect(authRedirect(const Unauthenticated(), '/onboarding', extraPublicPaths: {'/onboarding'}), isNull);
      expect(authRedirect(const Authenticated(UserProfile(id: 'u', role: AppRole.customer, status: 'active', fullName: 'A')), '/onboarding', extraPublicPaths: {'/onboarding'}), '/');
    });
    test('signed-in users are bounced off auth pages', () {
      final s = Authenticated(const UserProfile(id: 'u', role: AppRole.customer, status: 'active', fullName: 'A'));
      expect(authRedirect(s, '/login'), '/');
      expect(authRedirect(s, '/splash'), '/');
      expect(authRedirect(s, '/'), isNull);
    });
    test('gates', () {
      expect(authRedirect(const AuthInitializing(), '/'), '/splash');
      expect(authRedirect(const NeedsProfile(), '/'), '/complete-profile');
      expect(authRedirect(const AccountSuspended(), '/'), '/suspended');
      expect(authRedirect(const PasswordRecovery(), '/login'), '/reset-password');
    });
  });
}
