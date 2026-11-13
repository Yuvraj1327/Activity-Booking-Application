import 'package:flutter_shared/flutter_shared.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:zuruv/core/router/app_router.dart';

void main() {
  const signedOut = Unauthenticated();
  Authenticated signedIn(AppRole role) =>
      Authenticated(UserProfile(id: 'u', role: role, status: 'active', fullName: 'A'));

  group('launch rules', () {
    String? go(AppAuthState auth, String loc, {bool splash = true, bool onboarded = true}) =>
        launchRedirect(auth, loc, splashDone: splash, onboarded: onboarded);

    test('everyone waits on the splash first', () {
      expect(go(signedOut, '/', splash: false), '/splash');
      expect(go(signedIn(AppRole.customer), '/home', splash: false), '/splash');
      expect(go(signedIn(AppRole.owner), '/owner/dashboard', splash: false), '/splash');
      expect(go(signedOut, '/splash', splash: false), '/splash');
    });

    test('first launch signed out goes to onboarding, once', () {
      expect(go(signedOut, '/', onboarded: false), '/onboarding');
      expect(go(signedOut, '/login', onboarded: false), '/onboarding');
      expect(go(signedOut, '/onboarding', onboarded: false), isNull);
      expect(go(signedOut, '/onboarding'), '/login');
      expect(go(signedOut, '/register', onboarded: false), isNull); // deep links to sign-up still work
    });

    test('signed-in users never see the first-run onboarding rules', () {
      expect(go(signedIn(AppRole.customer), '/home', onboarded: false), isNull);
      expect(authRedirect(signedOut, '/home', extraPublicPaths: const {'/onboarding'}), '/login');
    });
  });

  group('role routing (one app, two dashboards)', () {
    test('signed-out and gated users are not touched (the auth guard decides)', () {
      expect(roleRedirect(signedOut, '/owner/dashboard'), isNull);
      expect(roleRedirect(const NeedsProfile(), '/home'), isNull);
    });

    test('customer: / opens the Customer Dashboard; owner pages are off limits', () {
      final c = signedIn(AppRole.customer);
      expect(roleRedirect(c, '/'), '/home');
      expect(roleRedirect(c, '/home'), isNull);
      expect(roleRedirect(c, '/bookings/b1'), isNull);
      expect(roleRedirect(c, '/owner'), '/home');
      expect(roleRedirect(c, '/owner/dashboard'), '/home');
      expect(roleRedirect(c, '/owner/venues/new'), '/home');
    });

    test('owner: / opens the Owner Dashboard; customer pages are off limits', () {
      final o = signedIn(AppRole.owner);
      expect(roleRedirect(o, '/'), '/owner/dashboard');
      expect(roleRedirect(o, '/owner/dashboard'), isNull);
      expect(roleRedirect(o, '/owner/venues/v1/courts'), isNull);
      expect(roleRedirect(o, '/home'), '/owner/dashboard');
      expect(roleRedirect(o, '/venues/v1/book'), '/owner/dashboard');
      expect(roleRedirect(o, '/ownership'), '/owner/dashboard'); // prefix match is on a path segment
    });

    test('owner intro is shown once after the first owner sign-in', () {
      final o = signedIn(AppRole.owner);
      expect(roleRedirect(o, '/', ownerOnboarded: false), '/owner/onboarding');
      expect(roleRedirect(o, '/owner/dashboard', ownerOnboarded: false), '/owner/onboarding');
      expect(roleRedirect(o, '/owner/onboarding', ownerOnboarded: false), isNull);
      // Customers never see it.
      expect(roleRedirect(signedIn(AppRole.customer), '/home', ownerOnboarded: false), isNull);
    });

    test('a tapped push opens the related booking in the right area', () {
      expect(pushRoute({'booking_id': 'b9'}, AppRole.customer), '/bookings/b9');
      expect(pushRoute({'booking_id': 'b9'}, AppRole.owner), '/owner/bookings/b9');
      expect(pushRoute({}, AppRole.customer), '/notifications');
      expect(pushRoute({'booking_id': ''}, AppRole.owner), '/owner/notifications');
    });
  });
}
