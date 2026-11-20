import 'package:go_router/go_router.dart';

import 'package:zuruv/core/settings/about_screens.dart';
import 'package:zuruv/core/settings/account_screen.dart';
import 'package:zuruv/core/settings/appearance_screen.dart';
import 'package:zuruv/core/settings/help_screens.dart';
import 'package:zuruv/core/settings/notification_settings_screen.dart';
import 'package:zuruv/core/settings/preferences_screen.dart';
import 'package:zuruv/core/settings/privacy_screen.dart';
import 'package:zuruv/core/settings/settings_screen.dart';

/// The same Settings screens for both roles, mounted under [base] (`/settings` for customers,
/// `/owner/settings` for owners, so the role guard keeps each role in its own area).
List<RouteBase> settingsRoutes(String base) => [
      GoRoute(path: base, builder: (_, __) => const SettingsScreen()),
      GoRoute(path: '$base/account', builder: (_, __) => const AccountScreen()),
      GoRoute(path: '$base/appearance', builder: (_, __) => const AppearanceScreen()),
      GoRoute(path: '$base/preferences', builder: (_, __) => const PreferencesScreen()),
      GoRoute(path: '$base/notifications', builder: (_, __) => const NotificationSettingsScreen()),
      GoRoute(path: '$base/privacy', builder: (_, __) => const PrivacyScreen()),
      GoRoute(path: '$base/help', builder: (_, __) => const HelpScreen()),
      GoRoute(path: '$base/help/messages', builder: (_, __) => const MyMessagesScreen()),
      GoRoute(path: '$base/help/:kind', builder: (_, s) => SupportFormScreen(kind: s.pathParameters['kind']!)),
      GoRoute(path: '$base/about', builder: (_, __) => const AboutScreen()),
      GoRoute(path: '$base/about/terms', builder: (_, __) => const LegalScreen(privacy: false)),
      GoRoute(path: '$base/about/privacy', builder: (_, __) => const LegalScreen(privacy: true)),
    ];
