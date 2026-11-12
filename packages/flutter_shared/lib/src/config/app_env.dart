/// Build-time configuration, supplied with `--dart-define-from-file=env/dev.json`.
///
/// Only PUBLIC values belong here (Supabase URL + anon key, API URL). The Supabase
/// service-role key and any other secret must never be added to a Flutter app.
class AppEnv {
  const AppEnv._();

  static const String supabaseUrl = String.fromEnvironment('SUPABASE_URL');
  static const String supabaseAnonKey = String.fromEnvironment('SUPABASE_ANON_KEY');
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:8008/api/v1',
  );

  /// Deep link Supabase redirects to after e-mail confirmation, password reset and OAuth,
  /// e.g. `io.zuruv.customer://login-callback`. Must also be allow-listed in the Supabase dashboard.
  static const String authRedirectUrl = String.fromEnvironment('AUTH_REDIRECT_URL');

  /// Sign-in methods are shown only when switched on, because each one needs dashboard setup
  /// (Google/Apple credentials, an SMS provider for phone). See docs/AUTHENTICATION_FLOW.md.
  static const bool googleAuthEnabled = bool.fromEnvironment('GOOGLE_AUTH_ENABLED');
  static const bool appleAuthEnabled = bool.fromEnvironment('APPLE_AUTH_ENABLED');
  static const bool phoneAuthEnabled = bool.fromEnvironment('PHONE_AUTH_ENABLED');

  static bool get supabaseConfigured => supabaseUrl.isNotEmpty && supabaseAnonKey.isNotEmpty;

  /// `GET /health` lives at the server root, outside the versioned prefix.
  static Uri get healthUri => Uri.parse(apiBaseUrl).replace(path: '/health', query: '');
}
