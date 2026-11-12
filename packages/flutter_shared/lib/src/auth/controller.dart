import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../network/api_exception.dart';
import 'gateway.dart';
import 'models.dart';
import 'providers.dart';
import 'state.dart';

class AuthController extends Notifier<AppAuthState> {
  bool _resolving = false;
  String? _pendingNotice;

  AuthGateway get _gateway => ref.read(authGatewayProvider);
  AppRole get _expectedRole => ref.read(expectedRoleProvider);

  @override
  AppAuthState build() {
    final gateway = ref.watch(authGatewayProvider);
    final sub = gateway.events.listen(_onEvent);
    ref.onDispose(sub.cancel);

    if (gateway.hasSession) {
      // Session restored from secure storage: confirm it with the API before showing the app.
      Future.microtask(resolve);
      return const AuthInitializing();
    }
    return const Unauthenticated();
  }

  void _onEvent(GatewayEvent event) {
    switch (event) {
      case GatewayEvent.signedIn:
        resolve();
      case GatewayEvent.signedOut:
        // Keep an explanation that was already set (the event can arrive before or after it).
        final current = state;
        if (current is Unauthenticated && current.notice != null) return;
        state = Unauthenticated(notice: _pendingNotice);
        _pendingNotice = null;
      case GatewayEvent.passwordRecovery:
        state = const PasswordRecovery();
    }
  }

  /// Asks the API who the signed-in user is and moves to the matching state.
  Future<void> resolve() async {
    if (_resolving) return;
    _resolving = true;
    try {
      if (state is! PasswordRecovery) state = const AuthInitializing();
      final me = await _gateway.fetchMe();
      if (state is PasswordRecovery) return;
      final profile = me.profile;
      if (profile == null) {
        await _handleMissingProfile(me);
      } else {
        await _handleProfile(profile);
      }
    } on ApiException catch (e) {
      if (e.statusCode == 401) {
        _pendingNotice = 'Your session has expired. Please sign in again.';
        await _gateway.signOut();
        state = Unauthenticated(notice: _pendingNotice);
        _pendingNotice = null;
      } else {
        state = AuthFailure(e.isNetworkError ? 'Cannot reach the server. Check your connection.' : e.message);
      }
    } catch (_) {
      state = const AuthFailure('Something went wrong. Please try again.');
    } finally {
      _resolving = false;
    }
  }

  Future<void> _handleProfile(UserProfile profile) async {
    if (profile.role != _expectedRole) {
      // The server says this account is another kind. Never let it into this app.
      _pendingNotice = 'This is a ${profile.role.label} account. '
          'Please use the ZURUV ${profile.role.label} app, or register a new ${_expectedRole.label} account.';
      await _gateway.signOut();
      state = Unauthenticated(notice: _pendingNotice);
      _pendingNotice = null;
      return;
    }
    state = profile.isActive ? Authenticated(profile) : const AccountSuspended();
  }

  Future<void> _handleMissingProfile(MeResponse me) async {
    final meta = _gateway.userMetadata;
    final name = (meta['full_name'] as String?)?.trim();
    final business = (meta['business_name'] as String?)?.trim();
    final complete = name != null &&
        name.isNotEmpty &&
        (_expectedRole != AppRole.owner || (business != null && business.isNotEmpty));
    if (complete) {
      // Registered through this app: create the profile without asking again.
      try {
        final profile = await _gateway.createProfile(CreateProfileRequest(
          role: _expectedRole,
          fullName: name,
          businessName: _expectedRole == AppRole.owner ? business : null,
        ));
        await _handleProfile(profile);
        return;
      } on ApiException catch (e) {
        if (e.statusCode == 409) {
          await resolveAfterConflict();
          return;
        }
        state = NeedsProfile(email: me.email, prefillName: name, prefillBusinessName: business, error: e.message);
        return;
      }
    }
    state = NeedsProfile(email: me.email, prefillName: name, prefillBusinessName: business);
  }

  Future<void> resolveAfterConflict() async {
    _resolving = false;
    await resolve();
  }

  // ------------------------------------------------------------------ actions used by screens

  Future<SignUpOutcome> register({
    required String email,
    required String password,
    required String fullName,
    String? businessName,
  }) =>
      _gateway.signUp(email: email, password: password, metadata: {
        'full_name': fullName,
        if (businessName != null) 'business_name': businessName,
      });

  Future<void> signIn(String email, String password) => _gateway.signIn(email: email, password: password);

  Future<void> signInWithOAuth(OAuthKind kind) => _gateway.signInWithOAuth(kind);

  Future<void> sendPhoneOtp(String phone) => _gateway.sendPhoneOtp(phone);

  Future<void> verifyPhoneOtp(String phone, String code) =>
      _gateway.verifyPhoneOtp(phone: phone, code: code);

  Future<void> sendPasswordReset(String email) => _gateway.sendPasswordReset(email);

  /// Finishes the reset-link flow. On success the signed-in session is resolved normally.
  Future<void> setNewPassword(String password) async {
    await _gateway.updatePassword(password);
    state = const AuthInitializing();
    await resolve();
  }

  /// Submits the "complete your profile" form.
  Future<void> completeProfile({required String fullName, String? businessName}) async {
    final current = state;
    try {
      final profile = await _gateway.createProfile(CreateProfileRequest(
        role: _expectedRole,
        fullName: fullName,
        businessName: _expectedRole == AppRole.owner ? businessName : null,
      ));
      await _handleProfile(profile);
    } on ApiException catch (e) {
      if (e.statusCode == 409) {
        await resolveAfterConflict();
        return;
      }
      state = NeedsProfile(
        email: current is NeedsProfile ? current.email : null,
        prefillName: fullName,
        prefillBusinessName: businessName,
        error: e.message,
      );
    }
  }

  /// Replaces the signed-in profile after the user edited it (name, phone, avatar).
  void setProfile(UserProfile profile) {
    if (state is Authenticated) state = Authenticated(profile);
  }

  Future<void> signOut() async {
    await _gateway.signOut();
    state = const Unauthenticated();
  }
}
