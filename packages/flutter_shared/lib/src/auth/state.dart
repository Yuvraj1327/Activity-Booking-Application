import 'models.dart';

/// Where the user is in the sign-in lifecycle. (Named `AppAuthState` to avoid clashing with
/// Supabase's own `AuthState`.)
sealed class AppAuthState {
  const AppAuthState();
}

/// Restoring a stored session / asking the API who the user is.
class AuthInitializing extends AppAuthState {
  const AuthInitializing();
}

class Unauthenticated extends AppAuthState {
  const Unauthenticated({this.notice});

  /// Shown on the login screen (e.g. "This is an owner account, use the Owner app").
  final String? notice;
}

/// Signed in with Supabase but no ZURUV profile yet.
class NeedsProfile extends AppAuthState {
  const NeedsProfile({this.email, this.prefillName, this.prefillBusinessName, this.error});

  final String? email;
  final String? prefillName;
  final String? prefillBusinessName;
  final String? error;
}

class Authenticated extends AppAuthState {
  const Authenticated(this.profile);
  final UserProfile profile;
}

class AccountSuspended extends AppAuthState {
  const AccountSuspended();
}

/// Signed in, but the API could not be reached or failed. The session is kept.
class AuthFailure extends AppAuthState {
  const AuthFailure(this.message);
  final String message;
}

/// The user opened a password-reset link and must choose a new password.
class PasswordRecovery extends AppAuthState {
  const PasswordRecovery();
}
