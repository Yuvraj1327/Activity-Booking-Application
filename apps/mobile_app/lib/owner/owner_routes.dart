import 'package:go_router/go_router.dart';

import '../core/settings/settings_routes.dart';
import 'features/analytics/analytics_screen.dart';
import 'features/bookings/booking_details_screen.dart';
import 'features/bookings/bookings_screen.dart';
import 'features/courts/courts_screen.dart';
import 'features/dashboard/dashboard_screen.dart';
import 'features/earnings/earnings_screen.dart';
import 'features/notifications/notifications_screen.dart';
import 'features/onboarding/onboarding_screen.dart';
import 'features/profile/business_info_screen.dart';
import 'features/profile/edit_profile_screen.dart';
import 'features/profile/payout_settings_screen.dart';
import 'features/profile/profile_screen.dart';
import 'features/reviews/reviews_screen.dart';
import 'features/schedules/manage_slots_screen.dart';
import 'features/shell/main_shell.dart';
import 'features/venue_form/venue_form_screen.dart';
import 'features/venues/venue_manage_screen.dart';
import 'features/venues/venues_screen.dart';

/// Every owner page lives under `/owner` so it can never clash with a customer path, and the
/// router can keep customers out of it with one prefix check.
const ownerPrefix = '/owner';

/// Where an owner lands after signing in.
const ownerHome = '/owner/dashboard';

/// Owner routes (all protected; the API also verifies the Owner role on every request).
List<RouteBase> ownerRoutes() => [
      GoRoute(path: '/owner', redirect: (_, __) => ownerHome),
      GoRoute(path: '/owner/onboarding', builder: (_, __) => const OnboardingScreen()),
      StatefulShellRoute.indexedStack(
        builder: (context, state, shell) => MainShell(shell: shell),
        branches: [
          StatefulShellBranch(routes: [GoRoute(path: '/owner/dashboard', builder: (_, __) => const DashboardScreen())]),
          StatefulShellBranch(routes: [GoRoute(path: '/owner/venues', builder: (_, __) => const VenuesScreen())]),
          StatefulShellBranch(routes: [GoRoute(path: '/owner/bookings', builder: (_, __) => const BookingsScreen())]),
          StatefulShellBranch(routes: [GoRoute(path: '/owner/earnings', builder: (_, __) => const EarningsScreen())]),
          StatefulShellBranch(routes: [GoRoute(path: '/owner/profile', builder: (_, __) => const ProfileScreen())]),
        ],
      ),
      // '/owner/venues/new' is declared before '/owner/venues/:id' so "new" is never read as a venue id.
      GoRoute(path: '/owner/venues/new', builder: (_, __) => const VenueFormScreen()),
      GoRoute(path: '/owner/venues/:id', builder: (_, s) => VenueManageScreen(venueId: s.pathParameters['id']!)),
      GoRoute(path: '/owner/venues/:id/edit', builder: (_, s) => VenueFormScreen(venueId: s.pathParameters['id'])),
      GoRoute(path: '/owner/venues/:id/courts', builder: (_, s) => CourtsScreen(venueId: s.pathParameters['id']!)),
      GoRoute(path: '/owner/venues/:id/slots', builder: (_, s) => ManageSlotsScreen(venueId: s.pathParameters['id']!)),
      GoRoute(path: '/owner/bookings/:id', builder: (_, s) => BookingDetailsScreen(bookingId: s.pathParameters['id']!)),
      GoRoute(path: '/owner/analytics', builder: (_, __) => const AnalyticsScreen()),
      GoRoute(path: '/owner/reviews', builder: (_, __) => const ReviewsScreen()),
      GoRoute(path: '/owner/notifications', builder: (_, __) => const NotificationsScreen()),
      GoRoute(path: '/owner/profile/edit', builder: (_, __) => const EditProfileScreen()),
      GoRoute(path: '/owner/profile/business', builder: (_, __) => const BusinessInfoScreen()),
      GoRoute(path: '/owner/profile/payout', builder: (_, __) => const PayoutSettingsScreen()),
      ...settingsRoutes('/owner/settings'),
    ];
