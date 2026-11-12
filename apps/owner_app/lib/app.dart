import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutter_shared/flutter_shared.dart';

import 'core/router/app_router.dart';
import 'core/theme/owner_theme.dart';

class ZuruvOwnerApp extends ConsumerWidget {
  const ZuruvOwnerApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);
    return MaterialApp.router(
      title: 'ZURUV Owner',
      debugShowCheckedModeBanner: false,
      theme: buildOwnerTheme(),
      routerConfig: router,
      builder: (context, child) => PushBootstrap(
        // A tapped push opens the related booking (ids only; the screen loads fresh data).
        onOpen: (data) => router.push(pushRoute(data)),
        child: child ?? const SizedBox.shrink(),
      ),
    );
  }
}
