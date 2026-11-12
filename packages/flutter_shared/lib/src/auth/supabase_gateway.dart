import 'package:dio/dio.dart';
import 'package:supabase_flutter/supabase_flutter.dart' as sb;

import '../config/app_env.dart';
import '../network/api_client.dart';
import 'gateway.dart';
import 'models.dart';

/// Production [AuthGateway]: Supabase Auth for credentials and sessions (stored securely and
/// refreshed automatically by the SDK), the ZURUV API for the profile, role and status.
class SupabaseAuthGateway implements AuthGateway {
  SupabaseAuthGateway(this._dio);

  final Dio _dio;

  sb.GoTrueClient get _auth => sb.Supabase.instance.client.auth;

  String? get _redirect => AppEnv.authRedirectUrl.isEmpty ? null : AppEnv.authRedirectUrl;

  @override
  bool get hasSession => AppEnv.supabaseConfigured && _auth.currentSession != null;

  @override
  Map<String, dynamic> get userMetadata => _auth.currentUser?.userMetadata ?? const {};

  @override
  Stream<GatewayEvent> get events {
    if (!AppEnv.supabaseConfigured) return const Stream.empty();
    return _auth.onAuthStateChange.map<GatewayEvent?>((state) {
      switch (state.event) {
        case sb.AuthChangeEvent.passwordRecovery:
          return GatewayEvent.passwordRecovery;
        case sb.AuthChangeEvent.signedIn:
        case sb.AuthChangeEvent.initialSession:
          return state.session != null ? GatewayEvent.signedIn : GatewayEvent.signedOut;
        case sb.AuthChangeEvent.signedOut:
          return GatewayEvent.signedOut;
        default:
          return null; // token refreshes etc. do not change who is signed in
      }
    }).where((e) => e != null).cast<GatewayEvent>();
  }

  Future<T> _guard<T>(Future<T> Function() action) async {
    if (!AppEnv.supabaseConfigured) {
      throw const AuthActionException('The app is not configured (missing Supabase settings).');
    }
    try {
      return await action();
    } on sb.AuthException catch (e) {
      throw AuthActionException(_friendly(e));
    }
  }

  static String _friendly(sb.AuthException e) {
    final code = e.code ?? '';
    if (code == 'invalid_credentials') return 'Incorrect e-mail or password.';
    if (code == 'email_not_confirmed') return 'Please verify your e-mail first. Check your inbox.';
    if (code == 'user_already_exists' || code == 'email_exists') {
      return 'An account with this e-mail already exists. Try signing in.';
    }
    if (code == 'weak_password') return 'Password is too weak. Use at least 8 characters.';
    if (code == 'over_request_rate_limit' || code == 'over_email_send_rate_limit') {
      return 'Too many attempts. Please wait a moment and try again.';
    }
    return e.message.isEmpty ? 'Something went wrong. Please try again.' : e.message;
  }

  @override
  Future<SignUpOutcome> signUp({
    required String email,
    required String password,
    required Map<String, dynamic> metadata,
  }) =>
      _guard(() async {
        final res = await _auth.signUp(
          email: email,
          password: password,
          data: metadata,
          emailRedirectTo: _redirect,
        );
        return res.session != null ? SignUpOutcome.signedIn : SignUpOutcome.confirmationRequired;
      });

  @override
  Future<void> signIn({required String email, required String password}) =>
      _guard(() => _auth.signInWithPassword(email: email, password: password));

  @override
  Future<void> signInWithOAuth(OAuthKind kind) => _guard(() async {
        await _auth.signInWithOAuth(
          kind == OAuthKind.google ? sb.OAuthProvider.google : sb.OAuthProvider.apple,
          redirectTo: _redirect,
        );
      });

  @override
  Future<void> sendPhoneOtp(String phone) => _guard(() => _auth.signInWithOtp(phone: phone));

  @override
  Future<void> verifyPhoneOtp({required String phone, required String code}) =>
      _guard(() => _auth.verifyOTP(phone: phone, token: code, type: sb.OtpType.sms));

  @override
  Future<void> sendPasswordReset(String email) =>
      _guard(() => _auth.resetPasswordForEmail(email, redirectTo: _redirect));

  @override
  Future<void> updatePassword(String newPassword) =>
      _guard(() => _auth.updateUser(sb.UserAttributes(password: newPassword)));

  @override
  Future<void> signOut() async {
    if (!AppEnv.supabaseConfigured) return;
    await _auth.signOut();
  }

  @override
  Future<MeResponse> fetchMe() async {
    try {
      final res = await _dio.get<Map<String, dynamic>>('/auth/me');
      return MeResponse.fromJson(res.data!);
    } catch (e) {
      throw toApiException(e);
    }
  }

  @override
  Future<UserProfile> createProfile(CreateProfileRequest request) async {
    try {
      final res = await _dio.post<Map<String, dynamic>>('/auth/profile', data: request.toJson());
      return UserProfile.fromJson(res.data!);
    } catch (e) {
      throw toApiException(e);
    }
  }
}
