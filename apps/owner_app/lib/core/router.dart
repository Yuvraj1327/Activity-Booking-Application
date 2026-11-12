import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:go_router/go_router.dart';

import '../features/home/home_screen.dart';

/// Auth routes and the redirect guard come from flutter_shared. Everything below is protected:
/// signed-out users are redirected to /login, wrong-role and suspended accounts never get in.
final routerProvider = Provider<GoRouter>((ref) {
  return buildAuthAwareRouter(
    ref,
    protectedRoutes: [
      GoRoute(path: '/', builder: (context, state) => const HomeScreen()),
    ],
  );
});
