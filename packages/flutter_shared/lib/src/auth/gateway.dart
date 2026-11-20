import 'models.dart';

/// Everything the auth layer needs from the outside world. The real implementation talks to
/// Supabase Auth and the ZURUV API; tests substitute a fake.
abstract class AuthGateway {
  bool get hasSession;

  /// `user_metadata` of the current user. Used only to PRE-FILL the profile form; it is
  /// editable by the user and never used for permissions.
  Map<String, dynamic> get userMetadata;

  /// Identity provider of the current user (`email`, `google`, ...), from Supabase `app_metadata`,
  /// which only the server can set. Used to keep social sign-ups at the customer role.
  String? get authProvider;

  Stream<GatewayEvent> get events;

  Future<SignUpOutcome> signUp({
    required String email,
    required String password,
    required Map<String, dynamic> metadata,
  });
  Future<void> signIn({required String email, required String password});
  Future<void> signInWithOAuth(OAuthKind kind);
  Future<void> sendPhoneOtp(String phone);
  Future<void> verifyPhoneOtp({required String phone, required String code});
  Future<void> sendPasswordReset(String email);
  Future<void> updatePassword(String newPassword);
  Future<void> signOut();

  /// Ends this session and every other session of the account (all devices).
  Future<void> signOutEverywhere();

  /// When the current session started signing in (null if unknown).
  DateTime? get sessionStartedAt;

  Future<MeResponse> fetchMe();
  Future<UserProfile> createProfile(CreateProfileRequest request);
}
