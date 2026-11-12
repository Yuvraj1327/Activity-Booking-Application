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

/// Which kind of account this app accepts. Each app overrides it in `main()`.
final expectedRoleProvider = Provider<AppRole>((ref) => throw UnimplementedError('override expectedRoleProvider'));

/// App-specific wording for the shared auth screens.
class AuthUiConfig {
  const AuthUiConfig({required this.appName, required this.role, this.tagline = 'Discover. Book. Play.'});

  final String appName;
  final AppRole role;
  final String tagline;

  bool get isOwner => role == AppRole.owner;
}

final authUiConfigProvider = Provider<AuthUiConfig>((ref) => throw UnimplementedError('override authUiConfigProvider'));

final authControllerProvider = NotifierProvider<AuthController, AppAuthState>(AuthController.new);

/// Work to do just before sign-out, while the session is still valid: removes this phone's push
/// token so a signed-out device stops receiving that account's notifications.
typedef SignOutHook = Future<void> Function();

final beforeSignOutProvider = Provider<SignOutHook>((ref) => () => ref.read(pushRegistrarProvider).unregister());
