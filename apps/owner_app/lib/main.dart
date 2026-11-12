import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';

import 'app.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Initialises Supabase when configured; it restores a stored session automatically.
  await initSupabase();
  runApp(
    ProviderScope(
      overrides: [
        expectedRoleProvider.overrideWithValue(AppRole.owner),
        authUiConfigProvider.overrideWithValue(
          const AuthUiConfig(appName: 'ZURUV Owner', role: AppRole.owner),
        ),
      ],
      child: const ZuruvOwnerApp(),
    ),
  );
}
