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
  final prefs = await SharedPreferences.getInstance();
  runApp(
    ProviderScope(
      overrides: [
        sharedPreferencesProvider.overrideWithValue(prefs),
        expectedRoleProvider.overrideWithValue(AppRole.customer),
        authUiConfigProvider.overrideWithValue(
          const AuthUiConfig(appName: 'ZURUV', role: AppRole.customer),
        ),
      ],
      child: const ZuruvCustomerApp(),
    ),
  );
}
