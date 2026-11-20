import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';

import 'core/router/app_router.dart';
import 'core/settings/app_settings.dart';
import 'core/theme/customer_theme.dart';
import 'core/theme/owner_theme.dart';
import 'customer/features/notifications/notifications_screen.dart' as customer_notifications;

class ZuruvApp extends ConsumerWidget {
  const ZuruvApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);
    // Each role keeps its own look. Before sign-in (and for customers) the customer theme applies.
    final isOwner = ref.watch(authControllerProvider.select((s) => s is Authenticated && s.profile.role == AppRole.owner));
    return MaterialApp.router(
      title: 'ZURUV',
      debugShowCheckedModeBanner: false,
      theme: isOwner ? buildOwnerTheme() : buildCustomerTheme(),
      darkTheme: isOwner ? buildOwnerTheme(brightness: Brightness.dark) : buildCustomerTheme(brightness: Brightness.dark),
      themeMode: ref.watch(themeModeProvider),
      locale: ref.watch(localeProvider),
      supportedLocales: [for (final code in supportedLanguages.keys) Locale(code)],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      routerConfig: router,
      builder: (context, child) => PushBootstrap(
        // A tapped push opens the related booking for the signed-in role (ids only; the screen
        // loads fresh data from the API).
        onOpen: (data) => router.push(pushRoute(data, ref.read(currentRoleProvider))),
        onForeground: (_) => ref.invalidate(customer_notifications.unreadCountProvider),
        child: child ?? const SizedBox.shrink(),
      ),
    );
  }
}
