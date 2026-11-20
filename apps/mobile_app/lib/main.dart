import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'app.dart';
import 'core/maps/maps_config.dart';
import 'core/storage/preferences.dart';

/// The one ZURUV mobile app. There is a single sign-in; the account's role (customer or venue
/// owner, read from the API/database) decides which dashboard opens.
Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Public runtime config from the bundled .env asset (see .env.example).
  await dotenv.load();
  // Web only: load the Google Maps JavaScript API with the key from .env (no-op elsewhere).
  await MapsConfig.initWeb();
  // Initialises Supabase when configured; it restores a stored session automatically.
  await initSupabase();
  // Firebase Cloud Messaging; a no-op if the native Firebase config files are not present.
  final push = await FirebasePushMessaging.init();
  final prefs = await SharedPreferences.getInstance();
  runApp(
    ProviderScope(
      overrides: [
        sharedPreferencesProvider.overrideWithValue(prefs),
        pushMessagingProvider.overrideWithValue(push),
        authUiConfigProvider.overrideWithValue(const AuthUiConfig(logoAsset: 'assets/images/logo.png', backgroundAsset: 'assets/images/onboarding/auth_background.png')),
      ],
      child: const ZuruvApp(),
    ),
  );
}
