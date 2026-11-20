import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/widgets.dart';
import 'package:go_router/go_router.dart';

import '../core/settings/settings_routes.dart';
import 'features/booking/booking_screen.dart';
import 'features/bookings/booking_details_screen.dart';
import 'features/bookings/bookings_screen.dart';
import 'features/categories/categories_provider.dart';
import 'features/discovery/venue_list_screen.dart';
import 'features/favorites/favorites_screen.dart';
import 'features/home/home_screen.dart';
import 'features/notifications/notifications_screen.dart';
import 'features/payments/payment_history_screen.dart';
import 'features/payments/payment_screen.dart';
import 'features/profile/edit_profile_screen.dart';
import 'features/profile/profile_screen.dart';
import 'features/shell/main_shell.dart';
import 'features/venue_details/venue_details_screen.dart';

/// Where a customer lands after signing in.
const customerHome = '/home';

/// Customer routes (all protected; the router also keeps owners out, see `roleRedirect`).
List<RouteBase> customerRoutes() => [
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
      ...settingsRoutes('/settings'),
    ];

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
