import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../network/api_client.dart';
import 'controller.dart';
import '../push/push_service.dart';
import 'gateway.dart';
import 'models.dart';
import 'state.dart';
import 'supabase_gateway.dart';

/// Shared API client (attaches the Supabase access token automatically).
final apiClientProvider = Provider<Dio>((ref) => createApiClient());

final authGatewayProvider = Provider<AuthGateway>((ref) => SupabaseAuthGateway(ref.watch(apiClientProvider)));

/// Account types a person may CHOOSE when registering in the mobile app. Admins never register
/// here: they are created in the database and sign in on the admin website only.
const signUpRoles = [AppRole.customer, AppRole.owner];

/// The account type picked on the register / complete-profile screens. It only decides which kind of
/// profile is REQUESTED the first time; from then on the role comes from the API (the database).
final signUpRoleProvider = StateProvider<AppRole>((ref) => AppRole.customer);

/// Wording for the shared auth screens.
class AuthUiConfig {
  const AuthUiConfig({this.appName = 'ZURUV', this.tagline = 'Discover. Book. Play.', this.logoAsset, this.backgroundAsset});

  /// Optional full-bleed background image shown behind the auth screens.
  final String? backgroundAsset;

  final String appName;

  /// App asset path of the brand logo shown on the auth screens (text name when null).
  final String? logoAsset;
  final String tagline;
}

final authUiConfigProvider = Provider<AuthUiConfig>((ref) => const AuthUiConfig());

final authControllerProvider = NotifierProvider<AuthController, AppAuthState>(AuthController.new);

/// Work to do just before sign-out, while the session is still valid: removes this phone's push
/// token so a signed-out device stops receiving that account's notifications.
typedef SignOutHook = Future<void> Function();

final beforeSignOutProvider = Provider<SignOutHook>((ref) => () => ref.read(pushRegistrarProvider).unregister());
