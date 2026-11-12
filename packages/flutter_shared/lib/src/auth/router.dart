import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'providers.dart';
import 'state.dart';
import 'ui/auth_screens.dart';

const _publicPaths = {'/login', '/register', '/forgot-password', '/phone'};
const _gatePaths = {'/splash', '/complete-profile', '/suspended', '/auth-error', '/reset-password'};

/// Single place that decides where each auth state may be. Pure and unit-testable.
///
/// [extraPublicPaths] are app-specific pages a signed-out user may see (e.g. onboarding).
String? authRedirect(AppAuthState state, String location, {Set<String> extraPublicPaths = const {}}) {
  String? only(String path) => location == path ? null : path;
  final isPublic = _publicPaths.contains(location) || extraPublicPaths.contains(location);
  return switch (state) {
    AuthInitializing() => only('/splash'),
    Unauthenticated() => isPublic ? null : '/login',
    NeedsProfile() => only('/complete-profile'),
    AccountSuspended() => only('/suspended'),
    AuthFailure() => only('/auth-error'),
    PasswordRecovery() => only('/reset-password'),
    Authenticated() => (isPublic || _gatePaths.contains(location)) ? '/' : null,
  };
}

/// Re-runs GoRouter's redirect whenever the auth state changes.
class AuthRouterRefresh extends ChangeNotifier {
  AuthRouterRefresh(Ref ref) {
    ref.listen(authControllerProvider, (_, __) => notifyListeners());
  }
}

/// The shared auth screens as routes. Apps add their protected routes next to these.
List<RouteBase> buildAuthRoutes({WidgetBuilder? splashBuilder}) => [
      GoRoute(
        path: '/splash',
        builder: (context, __) => splashBuilder != null ? splashBuilder(context) : const SplashScreen(),
      ),
      GoRoute(path: '/login', builder: (_, __) => const LoginScreen()),
      GoRoute(path: '/register', builder: (_, __) => const RegisterScreen()),
      GoRoute(path: '/forgot-password', builder: (_, __) => const ForgotPasswordScreen()),
      GoRoute(path: '/reset-password', builder: (_, __) => const ResetPasswordScreen()),
      GoRoute(path: '/phone', builder: (_, __) => const PhoneSignInScreen()),
      GoRoute(path: '/complete-profile', builder: (_, __) => const CompleteProfileScreen()),
      GoRoute(path: '/suspended', builder: (_, __) => const SuspendedScreen()),
      GoRoute(path: '/auth-error', builder: (_, __) => const AuthErrorScreen()),
    ];

/// Lets an app run its own rules BEFORE the auth guard (e.g. a branded splash and first-run
/// onboarding). Return null for "no opinion", the current location to stay put, or another path.
typedef PreAuthRedirect = String? Function(AppAuthState auth, String location);

GoRouter buildAuthAwareRouter(
  Ref ref, {
  required List<RouteBase> protectedRoutes,
  Set<String> extraPublicPaths = const {},
  PreAuthRedirect? preRedirect,
  Listenable? extraRefresh,
  WidgetBuilder? splashBuilder,
}) {
  final refresh = AuthRouterRefresh(ref);
  ref.onDispose(refresh.dispose);
  return GoRouter(
    initialLocation: '/',
    refreshListenable: extraRefresh == null ? refresh : Listenable.merge([refresh, extraRefresh]),
    redirect: (context, state) {
      final auth = ref.read(authControllerProvider);
      final location = state.matchedLocation;
      final pre = preRedirect?.call(auth, location);
      if (pre != null) return pre == location ? null : pre;
      return authRedirect(auth, location, extraPublicPaths: extraPublicPaths);
    },
    routes: [...buildAuthRoutes(splashBuilder: splashBuilder), ...protectedRoutes],
  );
}
