import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'app.dart';
import 'core/storage/preferences.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
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
        // Only accounts with the Owner role may use this app (the backend enforces it too).
        expectedRoleProvider.overrideWithValue(AppRole.owner),
        authUiConfigProvider.overrideWithValue(
          const AuthUiConfig(appName: 'ZURUV Owner', role: AppRole.owner),
        ),
      ],
      child: const ZuruvOwnerApp(),
    ),
  );
}
