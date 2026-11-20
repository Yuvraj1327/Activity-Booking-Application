import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';

import 'package:zuruv/core/storage/preferences.dart';

/// Light / Dark / System appearance. Kept on the device (it is a per-phone choice) and restored
/// at start-up before the first frame, so there is no flash of the wrong theme.
class ThemeModeController extends Notifier<ThemeMode> {
  static const _key = 'theme_mode_v1';

  @override
  ThemeMode build() {
    final saved = ref.read(sharedPreferencesProvider).getString(_key);
    return ThemeMode.values.firstWhere((m) => m.name == saved, orElse: () => ThemeMode.system);
  }

  Future<void> set(ThemeMode mode) async {
    state = mode;
    await ref.read(sharedPreferencesProvider).setString(_key, mode.name);
  }
}

final themeModeProvider = NotifierProvider<ThemeModeController, ThemeMode>(ThemeModeController.new);

const supportedLanguages = <String, String>{'en': 'English', 'hi': 'हिन्दी (Hindi)'};

/// The app language. The account's saved language wins once signed in (so it follows the user to a
/// new phone); before sign-in the last value used on this device applies.
final languageCodeProvider = Provider<String>((ref) {
  final auth = ref.watch(authControllerProvider);
  if (auth is Authenticated && supportedLanguages.containsKey(auth.profile.language)) return auth.profile.language;
  final saved = ref.read(sharedPreferencesProvider).getString('language_v1');
  return supportedLanguages.containsKey(saved) ? saved! : 'en';
});

final localeProvider = Provider<Locale>((ref) => Locale(ref.watch(languageCodeProvider)));

/// Remembers the language on this device for the next launch (called whenever it is changed).
Future<void> rememberLanguage(WidgetRef ref, String code) =>
    ref.read(sharedPreferencesProvider).setString('language_v1', code);

/// Settings pages live under `/owner` for owners (so the router can keep roles apart) and at the
/// top level for customers.
final settingsBaseProvider = Provider<String>((ref) {
  final auth = ref.watch(authControllerProvider);
  return auth is Authenticated && auth.profile.role == AppRole.owner ? '/owner/settings' : '/settings';
});

final isOwnerProvider = Provider<bool>((ref) {
  final auth = ref.watch(authControllerProvider);
  return auth is Authenticated && auth.profile.role == AppRole.owner;
});
