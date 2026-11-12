import 'package:flutter_shared/flutter_shared.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:zuruv_owner/core/router/app_router.dart';

void main() {
  const signedOut = Unauthenticated();
  final owner = Authenticated(const UserProfile(id: 'u', role: AppRole.owner, status: 'active', fullName: 'A'));

  String? go(AppAuthState auth, String loc, {bool splash = true, bool onboarded = true}) =>
      launchRedirect(auth, loc, splashDone: splash, onboarded: onboarded);

  test('everyone waits on the splash first', () {
    expect(go(signedOut, '/', splash: false), '/splash');
    expect(go(owner, '/dashboard', splash: false), '/splash');
  });

  test('first launch signed out goes to onboarding, once', () {
    expect(go(signedOut, '/', onboarded: false), '/onboarding');
    expect(go(signedOut, '/onboarding', onboarded: false), isNull);
    expect(go(signedOut, '/onboarding'), '/login');
    expect(go(signedOut, '/register', onboarded: false), isNull);
  });

  test('the shared guard still decides access', () {
    expect(authRedirect(signedOut, '/dashboard', extraPublicPaths: const {'/onboarding'}), '/login');
    expect(authRedirect(owner, '/dashboard'), isNull);
    expect(authRedirect(owner, '/login'), '/');
  });
}
