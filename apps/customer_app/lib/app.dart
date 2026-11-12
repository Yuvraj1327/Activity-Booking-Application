import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutter_shared/flutter_shared.dart';

import 'core/router/app_router.dart';
import 'features/notifications/notifications_screen.dart';
import 'core/theme/customer_theme.dart';

class ZuruvCustomerApp extends ConsumerWidget {
  const ZuruvCustomerApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);
    return MaterialApp.router(
      title: 'ZURUV',
      debugShowCheckedModeBanner: false,
      theme: buildCustomerTheme(),
      routerConfig: router,
      builder: (context, child) => PushBootstrap(
        // A tapped push opens the related booking (ids only; the screen loads fresh data).
        onOpen: (data) => router.push(pushRoute(data)),
        onForeground: (_) => ref.invalidate(unreadCountProvider),
        child: child ?? const SizedBox.shrink(),
      ),
    );
  }
}
