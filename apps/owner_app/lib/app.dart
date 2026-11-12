import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';

import 'core/router.dart';

class ZuruvOwnerApp extends ConsumerWidget {
  const ZuruvOwnerApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp.router(
      title: 'ZURUV Owner',
      debugShowCheckedModeBanner: false,
      theme: buildZuruvTheme(primary: ZuruvColors.ownerPrimary),
      routerConfig: ref.watch(routerProvider),
    );
  }
}
