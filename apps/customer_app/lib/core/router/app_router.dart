import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:go_router/go_router.dart';

import '../../features/categories/categories_provider.dart';
import '../../features/booking/booking_screen.dart';
import '../../features/bookings/booking_details_screen.dart';
import '../../features/bookings/bookings_screen.dart';
import '../../features/discovery/venue_list_screen.dart';
import '../../features/favorites/favorites_screen.dart';
import '../../features/home/home_screen.dart';
import '../../features/location/location_controller.dart';
import '../../features/notifications/notifications_screen.dart';
import '../../features/onboarding/onboarding_screen.dart';
import '../../features/payments/payment_history_screen.dart';
import '../../features/payments/payment_screen.dart';
import '../../features/profile/edit_profile_screen.dart';
import '../../features/profile/profile_screen.dart';
import '../../features/shell/main_shell.dart';
import '../../features/splash/splash_screen.dart';
import '../../features/venue_details/venue_details_screen.dart';

/// Pure launch rules, evaluated BEFORE the shared auth guard:
///  1. Hold on the splash until it has run its course.
///  2. First launch, signed out: show onboarding (once).
/// Everything else (login, protected routes, suspended, wrong role...) is decided by
/// `authRedirect` in flutter_shared, so the Step 3 guarantees are unchanged.
String? launchRedirect(AppAuthState auth, String location, {required bool splashDone, required bool onboarded}) {
  if (!splashDone) return '/splash';
  if (auth is Unauthenticated) {
    if (!onboarded && (location == '/' || location == '/login')) return '/onboarding';
    if (onboarded && location == '/onboarding') return '/login';
  }
  return null;
}

class _RouterRefresh extends ChangeNotifier {
  void ping() => notifyListeners();
}

/// Auth routes and the redirect guard come from flutter_shared. Every route below is protected:
/// signed-out users go to /login, wrong-role and suspended accounts never get in.
final routerProvider = Provider<GoRouter>((ref) {
  final refresh = _RouterRefresh();
  ref.onDispose(refresh.dispose);
  ref.listen<bool>(splashDoneProvider, (_, __) => refresh.ping());
  ref.listen<bool>(onboardingDoneProvider, (_, __) => refresh.ping());

  return buildAuthAwareRouter(
    ref,
    extraPublicPaths: const {'/onboarding'},
    extraRefresh: refresh,
    splashBuilder: (_) => const BrandedSplashScreen(),
    preRedirect: (auth, location) => launchRedirect(
      auth,
      location,
      splashDone: ref.read(splashDoneProvider),
      onboarded: ref.read(onboardingDoneProvider),
    ),
    protectedRoutes: [
      GoRoute(path: '/onboarding', builder: (_, __) => const OnboardingScreen()),
      GoRoute(path: '/', redirect: (_, __) => '/home'),
      StatefulShellRoute.indexedStack(
        builder: (context, state, shell) => MainShell(shell: shell),
        branches: [
          StatefulShellBranch(routes: [GoRoute(path: '/home', builder: (_, __) => const HomeScreen())]),
          StatefulShellBranch(routes: [GoRoute(path: '/explore', builder: (_, __) => const VenueListScreen())]),
          StatefulShellBranch(routes: [GoRoute(path: '/bookings', builder: (_, __) => const BookingsScreen())]),
          StatefulShellBranch(routes: [GoRoute(path: '/favorites', builder: (_, __) => const FavoritesScreen())]),
          StatefulShellBranch(routes: [GoRoute(path: '/profile', builder: (_, __) => const ProfileScreen())]),
        ],
      ),
      GoRoute(path: '/venues/:id/book', builder: (_, state) => BookingScreen(venueId: state.pathParameters['id']!)),
      GoRoute(path: '/bookings/:id/pay', builder: (_, state) => PaymentScreen(bookingId: state.pathParameters['id']!)),
      GoRoute(path: '/payments', builder: (_, __) => const PaymentHistoryScreen()),
      GoRoute(path: '/bookings/:id', builder: (_, state) => BookingDetailsScreen(bookingId: state.pathParameters['id']!)),
      GoRoute(path: '/venues/:id', builder: (_, state) => VenueDetailsScreen(venueId: state.pathParameters['id']!)),
      GoRoute(path: '/category/:slug', builder: (_, state) => _CategoryRoute(slug: state.pathParameters['slug']!)),
      GoRoute(path: '/notifications', builder: (_, __) => const NotificationsScreen()),
      GoRoute(path: '/profile/edit', builder: (_, __) => const EditProfileScreen()),
    ],
  );
});

/// Results page for one sport. The title comes from the API's category name.
class _CategoryRoute extends ConsumerWidget {
  const _CategoryRoute({required this.slug});
  final String slug;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final name = ref
        .watch(categoriesProvider)
        .valueOrNull
        ?.where((c) => c.slug == slug)
        .map((c) => c.name)
        .firstOrNull;
    return VenueListScreen(key: ValueKey(slug), fixedCategory: slug, title: name ?? 'Venues');
  }
}

/// Where a tapped push notification should open. Pushes carry ids only; the screen loads the data.
String pushRoute(Map<String, String> data) {
  final booking = data['booking_id'];
  if (booking != null && booking.isNotEmpty) return '/bookings/$booking';
  return '/notifications';
}
