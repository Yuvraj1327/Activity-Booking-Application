import 'package:flutter/foundation.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Google Maps configuration read from the bundled `.env` (public, restricted keys only).
///
/// The native Maps SDKs get their keys at build time (see `tool/sync_native_keys.sh`); the Dart side
/// only reads them to decide whether a map can be shown, so a missing key degrades to a friendly
/// fallback instead of a blank grey tile.
class MapsConfig {
  const MapsConfig._();

  static String _env(String name) => dotenv.isInitialized ? (dotenv.maybeGet(name) ?? '').trim() : '';

  /// Key for the Maps SDK on this platform ('' when not configured or unsupported).
  static String get nativeKey => switch (defaultTargetPlatform) {
        TargetPlatform.android => _env('GOOGLE_MAPS_API_KEY_ANDROID'),
        TargetPlatform.iOS => _env('GOOGLE_MAPS_API_KEY_IOS'),
        _ => '',
      };

  /// Maps SDK for Android / iOS only; web, macOS etc. use the fallback.
  static bool get isSupportedPlatform =>
      !kIsWeb && (defaultTargetPlatform == TargetPlatform.android || defaultTargetPlatform == TargetPlatform.iOS);

  static bool get mapsAvailable => isSupportedPlatform && nativeKey.isNotEmpty;

  /// Restricted Places key for direct autocomplete calls ('' = use the backend proxy only).
  static String get placesKey => _env('GOOGLE_PLACES_API_KEY');
}

/// Whether an interactive map can be shown. Overridable in tests.
final mapsAvailableProvider = Provider<bool>((ref) => MapsConfig.mapsAvailable);
