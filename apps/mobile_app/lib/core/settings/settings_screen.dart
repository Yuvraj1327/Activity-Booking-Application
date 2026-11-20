import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:go_router/go_router.dart';

import 'package:zuruv/core/constants/tokens.dart';
import 'package:zuruv/core/settings/app_settings.dart';
import 'package:zuruv/core/settings/settings_widgets.dart';
import 'package:zuruv/customer/features/profile/avatar_view.dart';

String themeModeLabel(ThemeMode m) => switch (m) {
      ThemeMode.light => 'Light',
      ThemeMode.dark => 'Dark',
      ThemeMode.system => 'System',
    };

/// Settings hub, opened from the Profile screen by both Customers and Venue Owners. Every row
/// opens a real screen; the rows differ slightly by role (customers get sports interests, owners
/// manage their business from the Profile screen instead).
class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final auth = ref.watch(authControllerProvider);
    if (auth is! Authenticated) return const Scaffold(body: LoadingView());
    final profile = auth.profile;
    final base = ref.watch(settingsBaseProvider);
    final isOwner = ref.watch(isOwnerProvider);
    final mode = ref.watch(themeModeProvider);
    final editRoute = isOwner ? '/owner/profile/edit' : '/profile/edit';

    return SettingsPage(
      title: 'Settings',
      children: [
        Card(
          margin: const EdgeInsets.only(top: Gap.sm),
          child: InkWell(
            borderRadius: BorderRadius.circular(16),
            onTap: () => context.push(editRoute),
            child: Padding(
              padding: const EdgeInsets.all(Gap.lg),
              child: Row(
                children: [
                  AvatarView(name: profile.fullName, path: profile.avatarPath, radius: 28),
                  const SizedBox(width: Gap.lg),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(profile.fullName, style: theme.textTheme.titleMedium, maxLines: 1, overflow: TextOverflow.ellipsis),
                        Text(
                          [profile.email, profile.phone].whereType<String>().where((e) => e.isNotEmpty).join(' · '),
                          style: theme.textTheme.bodySmall,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                        const SizedBox(height: 4),
                        Text(isOwner ? 'Venue owner' : 'Player', style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.primary, fontWeight: FontWeight.w600)),
                      ],
                    ),
                  ),
                  Icon(Icons.chevron_right_rounded, color: theme.colorScheme.onSurfaceVariant),
                ],
              ),
            ),
          ),
        ),
        SettingsGroup(title: 'Profile & account', children: [
          SettingsTile(icon: Icons.person_outline_rounded, title: 'Profile', subtitle: 'Name, phone and photo', onTap: () => context.push(editRoute)),
          SettingsTile(icon: Icons.manage_accounts_outlined, title: 'Account', subtitle: 'Password and account deletion', onTap: () => context.push('$base/account')),
        ]),
        SettingsGroup(title: 'App', children: [
          SettingsTile(icon: Icons.palette_outlined, title: 'Appearance', value: themeModeLabel(mode), onTap: () => context.push('$base/appearance')),
          SettingsTile(icon: Icons.tune_rounded, title: 'Preferences', subtitle: isOwner ? 'Language' : 'Sports, city and language', onTap: () => context.push('$base/preferences')),
          SettingsTile(icon: Icons.notifications_none_rounded, title: 'Notifications', subtitle: 'Push, e-mail, bookings and payments', onTap: () => context.push('$base/notifications')),
          SettingsTile(icon: Icons.lock_outline_rounded, title: 'Privacy & security', subtitle: 'Permissions, sessions and sign-out', onTap: () => context.push('$base/privacy')),
        ]),
        SettingsGroup(title: 'More', children: [
          SettingsTile(icon: Icons.help_outline_rounded, title: 'Help & support', subtitle: 'FAQs, contact, feedback', onTap: () => context.push('$base/help')),
          SettingsTile(icon: Icons.info_outline_rounded, title: 'About', subtitle: 'Version, terms and privacy policy', onTap: () => context.push('$base/about')),
        ]),
      ],
    );
  }
}
