import 'package:flutter_shared/flutter_shared.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:zuruv_customer/core/router/app_router.dart';

void main() {
  const signedOut = Unauthenticated();
  final signedIn = Authenticated(const UserProfile(id: 'u', role: AppRole.customer, status: 'active', fullName: 'A'));

  String? go(AppAuthState auth, String loc, {bool splash = true, bool onboarded = true}) =>
      launchRedirect(auth, loc, splashDone: splash, onboarded: onboarded);

  test('everyone waits on the splash first', () {
    expect(go(signedOut, '/', splash: false), '/splash');
    expect(go(signedIn, '/home', splash: false), '/splash');
    expect(go(signedOut, '/splash', splash: false), '/splash');
  });

  test('first launch signed out goes to onboarding, once', () {
    expect(go(signedOut, '/', onboarded: false), '/onboarding');
    expect(go(signedOut, '/login', onboarded: false), '/onboarding');
    expect(go(signedOut, '/onboarding', onboarded: false), isNull);
    expect(go(signedOut, '/onboarding'), '/login');
    expect(go(signedOut, '/register', onboarded: false), isNull); // deep links to sign-up still work
  });

  test('signed-in users never see onboarding rules; the auth guard still decides', () {
    expect(go(signedIn, '/home', onboarded: false), isNull);
    expect(authRedirect(signedOut, '/home', extraPublicPaths: const {'/onboarding'}), '/login');
  });
}
