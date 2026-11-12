import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/router/app_router.dart';
import 'core/theme/customer_theme.dart';

class ZuruvCustomerApp extends ConsumerWidget {
  const ZuruvCustomerApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp.router(
      title: 'ZURUV',
      debugShowCheckedModeBanner: false,
      theme: buildCustomerTheme(),
      routerConfig: ref.watch(routerProvider),
    );
  }
}
