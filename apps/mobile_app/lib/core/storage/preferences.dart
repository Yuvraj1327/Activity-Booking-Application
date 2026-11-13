import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Loaded once in `main()` and overridden there (and in tests), so reads are synchronous.
final sharedPreferencesProvider = Provider<SharedPreferences>(
  (ref) => throw UnimplementedError('override sharedPreferencesProvider'),
);

class PrefKeys {
  const PrefKeys._();
  static const onboardingDone = 'onboarding_done_v1';

  /// The owner intro, shown once after an owner's first sign-in.
  static const ownerOnboardingDone = 'owner_onboarding_done_v1';
  static const cityId = 'selected_city_id';
  static const cityName = 'selected_city_name';
}
