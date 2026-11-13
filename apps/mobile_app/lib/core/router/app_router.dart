import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:go_router/go_router.dart';

import '../../customer/customer_routes.dart';
import '../../owner/features/onboarding/onboarding_screen.dart' show ownerOnboardingDoneProvider;
import '../../owner/owner_routes.dart';
import '../onboarding/onboarding_screen.dart';
import '../splash/splash_screen.dart';

/// Pure launch rules, evaluated BEFORE the shared auth guard:
///  1. Hold on the splash until it has run its course.
///  2. First launch, signed out: show onboarding (once).
/// Everything else (login, protected routes, suspended, ...) is decided by `authRedirect` in
/// flutter_shared, so the Step 3 guarantees are unchanged.
String? launchRedirect(AppAuthState auth, String location, {required bool splashDone, required bool onboarded}) {
  if (!splashDone) return '/splash';
  if (auth is Unauthenticated) {
    if (!onboarded && (location == '/' || location == '/login')) return '/onboarding';
    if (onboarded && location == '/onboarding') return '/login';
  }
  return null;
}

/// Pages every signed-in role may be on while the auth guard sorts them out (login, splash, ...).
const _authPaths = {
  '/login', '/register', '/forgot-password', '/phone', '/splash', '/complete-profile',
  '/suspended', '/auth-error', '/reset-password', '/onboarding',
};

bool _inOwnerArea(String location) => location == ownerPrefix || location.startsWith('$ownerPrefix/');

/// One app, two roles: after sign-in each role gets its own dashboard and cannot open the other's
/// pages. The role comes from the API (the database), never from the app or the token. This is a
/// UX boundary only: the backend enforces the same roles on every request.
///
///  * `/` opens the role's home (Customer -> Customer Dashboard, Venue Owner -> Owner Dashboard).
///  * A customer on an `/owner/...` page goes home; an owner on a customer page goes to the dashboard.
///  * An owner sees the owner intro once, right after the first sign-in.
String? roleRedirect(AppAuthState auth, String location, {bool ownerOnboarded = true}) {
  if (auth is! Authenticated) return null;
  switch (auth.profile.role) {
    case AppRole.owner:
      if (_authPaths.contains(location)) return null; // the auth guard moves these to '/'
      if (location == '/') return ownerOnboarded ? ownerHome : '$ownerPrefix/onboarding';
      if (!_inOwnerArea(location)) return ownerHome;
      if (!ownerOnboarded && location != '$ownerPrefix/onboarding') return '$ownerPrefix/onboarding';
      return null;
    case AppRole.customer:
      if (location == '/') return customerHome;
      if (_inOwnerArea(location)) return customerHome;
      return null;
    case AppRole.admin:
      return null; // never reaches here: the auth controller signs admins out (website only)
  }
}

/// The signed-in account's role, or null while signed out.
final currentRoleProvider = Provider<AppRole?>((ref) {
  final auth = ref.watch(authControllerProvider);
  return auth is Authenticated ? auth.profile.role : null;
});

class _RouterRefresh extends ChangeNotifier {
  void ping() => notifyListeners();
}

/// Auth routes and the redirect guard come from flutter_shared. Every route below is protected:
/// signed-out users go to /login, suspended accounts never get in, and each role only sees its own pages.
final routerProvider = Provider<GoRouter>((ref) {
  final refresh = _RouterRefresh();
  ref.onDispose(refresh.dispose);
  ref.listen<bool>(splashDoneProvider, (_, __) => refresh.ping());
  ref.listen<bool>(onboardingDoneProvider, (_, __) => refresh.ping());
  ref.listen<bool>(ownerOnboardingDoneProvider, (_, __) => refresh.ping());

  return buildAuthAwareRouter(
    ref,
    extraPublicPaths: const {'/onboarding'},
    extraRefresh: refresh,
    splashBuilder: (_) => const BrandedSplashScreen(),
    preRedirect: (auth, location) =>
        launchRedirect(
          auth,
          location,
          splashDone: ref.read(splashDoneProvider),
          onboarded: ref.read(onboardingDoneProvider),
        ) ??
        roleRedirect(auth, location, ownerOnboarded: ref.read(ownerOnboardingDoneProvider)),
    protectedRoutes: [
      GoRoute(path: '/onboarding', builder: (_, __) => const OnboardingScreen()),
      // '/' itself is always redirected by `roleRedirect` once signed in.
      GoRoute(path: '/', redirect: (_, __) => customerHome),
      ...customerRoutes(),
      ...ownerRoutes(),
    ],
  );
});

/// Where a tapped push notification should open for [role]. Pushes carry ids only; the screen loads the data.
String pushRoute(Map<String, String> data, AppRole? role) {
  final prefix = role == AppRole.owner ? ownerPrefix : '';
  final booking = data['booking_id'];
  if (booking != null && booking.isNotEmpty) return '$prefix/bookings/$booking';
  return '$prefix/notifications';
}
