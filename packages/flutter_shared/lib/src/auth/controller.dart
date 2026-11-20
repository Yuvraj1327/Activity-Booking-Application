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
        await _signOutWithNotice('Your session has expired. Please sign in again.');
      } else {
        state = AuthFailure(e.isNetworkError ? 'Cannot reach the server. Check your connection.' : e.message);
      }
    } catch (_) {
      state = const AuthFailure('Something went wrong. Please try again.');
    } finally {
      _resolving = false;
    }
  }

  /// Signs out and leaves [notice] on the login screen. The sign-out event may arrive before or
  /// after this returns, so the notice is held in a local too (never read back from the field).
  Future<void> _signOutWithNotice(String notice) async {
    _pendingNotice = notice;
    await _gateway.signOut();
    state = Unauthenticated(notice: notice);
    _pendingNotice = null;
  }

  Future<void> _handleProfile(UserProfile profile) async {
    if (profile.role == AppRole.admin) {
      // Admins use the website only. The API enforces every role again on each request.
      await _signOutWithNotice('Admin accounts sign in on the ZURUV admin website, not in the mobile app.');
      return;
    }
    state = profile.isActive ? Authenticated(profile) : const AccountSuspended();
  }

  Future<void> _handleMissingProfile(MeResponse me) async {
    final meta = _gateway.userMetadata;
    final social = _isSocialSignUp;
    final name = ((meta['full_name'] ?? meta['name']) as String?)?.trim();
    final business = (meta['business_name'] as String?)?.trim();
    // Registered through this app: the chosen account type travelled in the sign-up metadata.
    // Only customer/owner can be requested; anything else falls back to customer (the API rejects admin).
    // Social (Google) sign-ups are ALWAYS customers: user_metadata is user-editable and the provider
    // is not a vetted business, so Owner can only come from e-mail sign-up (or an admin).
    final requested = social ? AppRole.customer : AppRole.parse(meta['requested_role'] as String?);
    final role = requested == AppRole.owner ? AppRole.owner : AppRole.customer;
    final complete = name != null &&
        name.isNotEmpty &&
        (role != AppRole.owner || (business != null && business.isNotEmpty));
    if (complete) {
      // Registered through this app: create the profile without asking again.
      try {
        final profile = await _gateway.createProfile(CreateProfileRequest(
          role: role,
          fullName: name,
          businessName: role == AppRole.owner ? business : null,
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

  bool get _isSocialSignUp => _gateway.authProvider == 'google';

  /// True when the account type is fixed to customer (shown by the profile form).
  bool get isSocialSignUp => _isSocialSignUp;

  Future<void> resolveAfterConflict() async {
    _resolving = false;
    await resolve();
  }

  // ------------------------------------------------------------------ actions used by screens

  Future<SignUpOutcome> register({
    required String email,
    required String password,
    required String fullName,
    AppRole role = AppRole.customer,
    String? businessName,
  }) =>
      _gateway.signUp(email: email, password: password, metadata: {
        'full_name': fullName,
        'requested_role': (role == AppRole.owner ? AppRole.owner : AppRole.customer).name,
        if (role == AppRole.owner && businessName != null) 'business_name': businessName,
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
  Future<void> completeProfile({required AppRole role, required String fullName, String? businessName}) async {
    final current = state;
    try {
      final profile = await _gateway.createProfile(CreateProfileRequest(
        role: !_isSocialSignUp && role == AppRole.owner ? AppRole.owner : AppRole.customer,
        fullName: fullName,
        businessName: !_isSocialSignUp && role == AppRole.owner ? businessName : null,
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

  /// Changes the password of the signed-in user. The current password is checked first by signing
  /// in again with it, so a borrowed unlocked phone cannot silently take over the account.
  Future<void> changePassword({required String currentPassword, required String newPassword}) async {
    final s = state;
    final email = s is Authenticated ? s.profile.email : null;
    if (email == null || email.isEmpty) {
      throw const AuthActionException('Your account has no e-mail address to verify with.');
    }
    await _gateway.signIn(email: email, password: currentPassword);
    await _gateway.updatePassword(newPassword);
  }

  /// Signs out this device AND every other device the account is signed in on.
  Future<void> signOutEverywhere() async {
    try {
      await ref.read(beforeSignOutProvider)();
    } catch (_) {}
    await _gateway.signOutEverywhere();
    state = const Unauthenticated();
  }

  DateTime? get sessionStartedAt => _gateway.sessionStartedAt;

  Future<void> signOut() async {
    // Stop pushes for this account on this phone BEFORE the session (and its token) goes away.
    try {
      await ref.read(beforeSignOutProvider)();
    } catch (_) {}
    await _gateway.signOut();
    state = const Unauthenticated();
  }
}
