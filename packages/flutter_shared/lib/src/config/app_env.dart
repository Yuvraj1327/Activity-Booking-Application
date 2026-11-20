import 'package:flutter/foundation.dart' show kDebugMode;
import 'package:flutter_dotenv/flutter_dotenv.dart';

/// Runtime configuration loaded from the app's `.env` asset via `flutter_dotenv`
/// (each app calls `dotenv.load()` in `main()` before using this class).
///
/// Only PUBLIC values belong here (Supabase URL + anon key, API URL). The Supabase
/// service-role key and any other secret must never be added to a Flutter app.
/// If dotenv is not loaded (e.g. in unit tests) every value falls back to empty/false.
class AppEnv {
  const AppEnv._();

  static String _get(String key) => dotenv.isInitialized ? (dotenv.maybeGet(key) ?? '').trim() : '';

  static bool _flag(String key) => _get(key).toLowerCase() == 'true';

  static String get supabaseUrl => _get('SUPABASE_URL');
  static String get supabaseAnonKey => _get('SUPABASE_ANON_KEY');

  /// Required in profile/release builds. Only debug builds fall back to the local backend
  /// (port 8008), so a production build can never silently talk to localhost.
  static String get apiBaseUrl {
    final v = _get('API_BASE_URL');
    if (v.isNotEmpty) return v;
    if (kDebugMode) return 'http://localhost:8008/api/v1';
    throw StateError('API_BASE_URL is not set. Add it to the app\'s .env file.');
  }

  /// Deep link Supabase redirects to after e-mail confirmation, password reset and OAuth,
  /// e.g. `io.zuruv.app://login-callback`. Must also be allow-listed in the Supabase dashboard.
  static String get authRedirectUrl => _get('AUTH_REDIRECT_URL');

  /// Sign-in methods are shown only when switched on, because each one needs dashboard setup
  /// (Google/Apple credentials, an SMS provider for phone). See docs/AUTHENTICATION_FLOW.md.
  static bool get googleAuthEnabled => _flag('GOOGLE_AUTH_ENABLED');
  static bool get appleAuthEnabled => _flag('APPLE_AUTH_ENABLED');
  static bool get phoneAuthEnabled => _flag('PHONE_AUTH_ENABLED');

  /// OAuth *Web* client ID (Google Cloud Console). Also the client ID pasted into Supabase's Google
  /// provider; Google puts it in the ID token's audience so Supabase accepts the token. Public value.
  /// When empty, Google sign-in falls back to Supabase's browser (redirect) flow.
  static String get googleWebClientId => _get('GOOGLE_WEB_CLIENT_ID');

  /// OAuth *iOS* client ID (bundle id com.zuruv.zuruv). Public value; used on iOS only.
  static String get googleIosClientId => _get('GOOGLE_IOS_CLIENT_ID');

  static bool get supabaseConfigured => supabaseUrl.isNotEmpty && supabaseAnonKey.isNotEmpty;

  /// `GET /health` lives at the server root, outside the versioned prefix.
  static Uri get healthUri => Uri.parse(apiBaseUrl).replace(path: '/health', query: '');
}
