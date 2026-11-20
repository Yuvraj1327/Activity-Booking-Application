enum AppRole {
  customer,
  owner,
  admin;

  static AppRole? parse(String? value) {
    for (final role in AppRole.values) {
      if (role.name == value) return role;
    }
    return null;
  }

  String get label => switch (this) {
        AppRole.customer => 'customer',
        AppRole.owner => 'venue owner',
        AppRole.admin => 'admin',
      };
}

/// The account profile as returned by the ZURUV API. Role and status are authoritative
/// there; the app never decides them.
class UserProfile {
  const UserProfile({
    required this.id,
    required this.role,
    required this.status,
    required this.fullName,
    this.email,
    this.phone,
    this.avatarPath,
    this.language = 'en',
    this.deletionRequestedAt,
  });

  factory UserProfile.fromJson(Map<String, dynamic> json) => UserProfile(
        id: json['id'] as String,
        role: AppRole.parse(json['role'] as String?) ?? AppRole.customer,
        status: json['status'] as String? ?? 'active',
        fullName: json['full_name'] as String? ?? '',
        email: json['email'] as String?,
        phone: json['phone'] as String?,
        avatarPath: json['avatar_path'] as String?,
        language: json['language'] as String? ?? 'en',
        deletionRequestedAt: json['deletion_requested_at'] == null
            ? null
            : DateTime.tryParse(json['deletion_requested_at'] as String),
      );

  final String id;
  final AppRole role;
  final String status;
  final String fullName;
  final String? email;
  final String? phone;
  final String? avatarPath;

  /// Preferred language code (`en`, `hi`), stored on the account.
  final String language;

  /// Set while an account-deletion request is waiting for an administrator.
  final DateTime? deletionRequestedAt;

  bool get isActive => status == 'active';
}

/// Response of `GET /auth/me`.
class MeResponse {
  const MeResponse({required this.userId, this.email, required this.hasProfile, this.profile});

  factory MeResponse.fromJson(Map<String, dynamic> json) => MeResponse(
        userId: json['user_id'] as String,
        email: json['email'] as String?,
        hasProfile: json['has_profile'] as bool? ?? false,
        profile: json['profile'] == null
            ? null
            : UserProfile.fromJson(json['profile'] as Map<String, dynamic>),
      );

  final String userId;
  final String? email;
  final bool hasProfile;
  final UserProfile? profile;
}

/// Body of `POST /auth/profile`. Only customer or owner can be requested; the server
/// rejects anything else.
class CreateProfileRequest {
  const CreateProfileRequest({required this.role, required this.fullName, this.businessName});

  final AppRole role;
  final String fullName;
  final String? businessName;

  Map<String, dynamic> toJson() => {
        'role': role.name,
        'full_name': fullName,
        if (businessName != null) 'business_name': businessName,
      };
}

enum SignUpOutcome { signedIn, confirmationRequired }

enum OAuthKind { google, apple }

enum GatewayEvent { signedIn, signedOut, passwordRecovery }

/// The user closed the sign-in sheet. Not an error: screens show nothing.
class AuthCancelledException implements Exception {
  const AuthCancelledException();
  @override
  String toString() => 'cancelled';
}

/// A user-facing failure of a sign-in action (wrong password, weak password, ...).
class AuthActionException implements Exception {
  const AuthActionException(this.message);
  final String message;
  @override
  String toString() => message;
}
