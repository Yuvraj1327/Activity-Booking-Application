import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:go_router/go_router.dart';

import '../../features/analytics/analytics_screen.dart';
import '../../features/bookings/booking_details_screen.dart';
import '../../features/bookings/bookings_screen.dart';
import '../../features/dashboard/dashboard_screen.dart';
import '../../features/earnings/earnings_screen.dart';
import '../../features/notifications/notifications_screen.dart';
import '../../features/onboarding/onboarding_screen.dart';
import '../../features/profile/business_info_screen.dart';
import '../../features/profile/edit_profile_screen.dart';
import '../../features/profile/info_pages.dart';
import '../../features/profile/notification_prefs_screen.dart';
import '../../features/profile/payout_settings_screen.dart';
import '../../features/profile/profile_screen.dart';
import '../../features/reviews/reviews_screen.dart';
import '../../features/courts/courts_screen.dart';
import '../../features/schedules/manage_slots_screen.dart';
import '../../features/shell/main_shell.dart';
import '../../features/splash/splash_screen.dart';
import '../../features/venue_form/venue_form_screen.dart';
import '../../features/venues/venue_manage_screen.dart';
import '../../features/venues/venues_screen.dart';

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

/// Every route below is protected: signed-out users go to /login, and customers, admins and
/// suspended accounts never get in (decided by the shared guard).
final routerProvider = Provider<GoRouter>((ref) {
  final refresh = _RouterRefresh();
  ref.onDispose(refresh.dispose);
  ref.listen<bool>(splashDoneProvider, (_, __) => refresh.ping());
  ref.listen<bool>(onboardingDoneProvider, (_, __) => refresh.ping());

  return buildAuthAwareRouter(
    ref,
    extraPublicPaths: const {'/onboarding'},
    extraRefresh: refresh,
    splashBuilder: (_) => const OwnerSplashScreen(),
    preRedirect: (auth, location) => launchRedirect(
      auth,
      location,
      splashDone: ref.read(splashDoneProvider),
      onboarded: ref.read(onboardingDoneProvider),
    ),
    protectedRoutes: [
      GoRoute(path: '/onboarding', builder: (_, __) => const OnboardingScreen()),
      GoRoute(path: '/', redirect: (_, __) => '/dashboard'),
      StatefulShellRoute.indexedStack(
        builder: (context, state, shell) => MainShell(shell: shell),
        branches: [
          StatefulShellBranch(routes: [GoRoute(path: '/dashboard', builder: (_, __) => const DashboardScreen())]),
          StatefulShellBranch(routes: [GoRoute(path: '/venues', builder: (_, __) => const VenuesScreen())]),
          StatefulShellBranch(routes: [GoRoute(path: '/bookings', builder: (_, __) => const BookingsScreen())]),
          StatefulShellBranch(routes: [GoRoute(path: '/earnings', builder: (_, __) => const EarningsScreen())]),
          StatefulShellBranch(routes: [GoRoute(path: '/profile', builder: (_, __) => const ProfileScreen())]),
        ],
      ),
      // '/venues/new' is declared before '/venues/:id' so "new" is never read as a venue id.
      GoRoute(path: '/venues/new', builder: (_, __) => const VenueFormScreen()),
      GoRoute(path: '/venues/:id', builder: (_, s) => VenueManageScreen(venueId: s.pathParameters['id']!)),
      GoRoute(path: '/venues/:id/edit', builder: (_, s) => VenueFormScreen(venueId: s.pathParameters['id'])),
      GoRoute(path: '/venues/:id/courts', builder: (_, s) => CourtsScreen(venueId: s.pathParameters['id']!)),
      GoRoute(path: '/venues/:id/slots', builder: (_, s) => ManageSlotsScreen(venueId: s.pathParameters['id']!)),
      GoRoute(path: '/bookings/:id', builder: (_, s) => BookingDetailsScreen(bookingId: s.pathParameters['id']!)),
      GoRoute(path: '/analytics', builder: (_, __) => const AnalyticsScreen()),
      GoRoute(path: '/reviews', builder: (_, __) => const ReviewsScreen()),
      GoRoute(path: '/notifications', builder: (_, __) => const NotificationsScreen()),
      GoRoute(path: '/profile/edit', builder: (_, __) => const EditProfileScreen()),
      GoRoute(path: '/profile/business', builder: (_, __) => const BusinessInfoScreen()),
      GoRoute(path: '/profile/payout', builder: (_, __) => const PayoutSettingsScreen()),
      GoRoute(path: '/profile/notifications', builder: (_, __) => const NotificationPrefsScreen()),
      GoRoute(path: '/profile/help', builder: (_, __) => const HelpScreen()),
      GoRoute(path: '/profile/terms', builder: (_, __) => const TermsScreen()),
    ],
  );
});

/// Where a tapped push notification should open. Pushes carry ids only; the screen loads the data.
String pushRoute(Map<String, String> data) {
  final booking = data['booking_id'];
  if (booking != null && booking.isNotEmpty) return '/bookings/$booking';
  return '/notifications';
}
