import 'dart:async';

import '../auth/gateway.dart';
import '../auth/models.dart';
import '../network/api_exception.dart';

/// In-memory [AuthGateway] for widget and unit tests. Not used by the shipped apps.
class FakeAuthGateway implements AuthGateway {
  FakeAuthGateway({
    this.hasSession = false,
    this.authProvider,
    this.me,
    this.meError,
    Map<String, dynamic>? metadata,
  }) : userMetadata = metadata ?? <String, dynamic>{};

  @override
  bool hasSession;
  @override
  Map<String, dynamic> userMetadata;
  @override
  String? authProvider;

  /// When set, `signInWithOAuth` throws it (e.g. [AuthCancelledException]).
  Object? oauthError;

  /// What `GET /auth/me` returns.
  MeResponse? me;
  ApiException? meError;
  ApiException? createProfileError;

  final _events = StreamController<GatewayEvent>.broadcast();
  final List<String> calls = [];
  CreateProfileRequest? lastCreateRequest;

  @override
  Stream<GatewayEvent> get events => _events.stream;

  void emit(GatewayEvent e) => _events.add(e);

  @override
  Future<MeResponse> fetchMe() async {
    calls.add('fetchMe');
    if (meError != null) throw meError!;
    return me!;
  }

  @override
  Future<UserProfile> createProfile(CreateProfileRequest request) async {
    calls.add('createProfile');
    lastCreateRequest = request;
    if (createProfileError != null) throw createProfileError!;
    final profile = UserProfile(
      id: 'u1',
      role: request.role,
      status: 'active',
      fullName: request.fullName,
    );
    me = MeResponse(userId: 'u1', hasProfile: true, profile: profile);
    return profile;
  }

  @override
  Future<void> signIn({required String email, required String password}) async {
    calls.add('signIn');
    if (password == 'wrong') throw const AuthActionException('Incorrect e-mail or password.');
    hasSession = true;
    emit(GatewayEvent.signedIn);
  }

  @override
  Future<SignUpOutcome> signUp({
    required String email,
    required String password,
    required Map<String, dynamic> metadata,
  }) async {
    calls.add('signUp');
    userMetadata = metadata;
    return SignUpOutcome.confirmationRequired;
  }

  @override
  Future<void> signOut() async {
    calls.add('signOut');
    hasSession = false;
    emit(GatewayEvent.signedOut);
  }

  @override
  Future<void> signOutEverywhere() async {
    calls.add('signOutEverywhere');
    hasSession = false;
    emit(GatewayEvent.signedOut);
  }

  @override
  DateTime? get sessionStartedAt => null;

  @override
  Future<void> signInWithOAuth(OAuthKind kind) async {
    calls.add('oauth:${kind.name}');
    if (oauthError != null) throw oauthError!;
  }
  @override
  Future<void> sendPhoneOtp(String phone) async => calls.add('sendPhoneOtp');
  @override
  Future<void> verifyPhoneOtp({required String phone, required String code}) async => calls.add('verifyPhoneOtp');
  @override
  Future<void> sendPasswordReset(String email) async => calls.add('sendPasswordReset');
  @override
  Future<void> updatePassword(String newPassword) async => calls.add('updatePassword');
}
