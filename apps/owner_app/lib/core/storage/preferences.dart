import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Loaded once in `main()` and overridden there (and in tests), so reads are synchronous.
final sharedPreferencesProvider = Provider<SharedPreferences>(
  (ref) => throw UnimplementedError('override sharedPreferencesProvider'),
);

class PrefKeys {
  const PrefKeys._();
  static const onboardingDone = 'onboarding_done_v1';
}

/// Device-local owner settings (notification preferences are not stored on the server yet).
class OwnerPrefKeys {
  const OwnerPrefKeys._();
  static const notifyBookings = 'notify_bookings';
  static const notifyPayments = 'notify_payments';
  static const notifyReviews = 'notify_reviews';
}
