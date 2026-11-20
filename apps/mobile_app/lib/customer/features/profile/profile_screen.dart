import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:go_router/go_router.dart';

import 'package:zuruv/core/constants/tokens.dart';
import 'package:zuruv/customer/features/location/location_controller.dart';
import 'package:zuruv/customer/features/location/location_sheet.dart';
import 'package:zuruv/customer/features/profile/avatar_view.dart';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final auth = ref.watch(authControllerProvider);
    if (auth is! Authenticated) return const Scaffold(body: LoadingView());
    final profile = auth.profile;
    final city = ref.watch(locationControllerProvider.select((s) => s.city));
    final contact = [profile.email, profile.phone]
        .whereType<String>()
        .where((e) => e.isNotEmpty)
        .join('  ·  ');

    final primary = theme.colorScheme.primary;
    final onHeader = theme.colorScheme.onPrimary;

    return Scaffold(
      body: ListView(
        padding: EdgeInsets.zero,
        children: [
          Container(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  Color.lerp(primary, Colors.white, 0.18)!,
                  primary,
                  Color.lerp(primary, Colors.black, 0.25)!
                ],
              ),
              borderRadius:
                  const BorderRadius.vertical(bottom: Radius.circular(32)),
            ),
            child: SafeArea(
              bottom: false,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(Gap.page, 12, Gap.page, 24),
                child: Column(
                  children: [
                    Align(
                      alignment: Alignment.centerLeft,
                      child: Text('Profile',
                          style: theme.textTheme.titleLarge?.copyWith(
                              color: onHeader, fontWeight: FontWeight.w700)),
                    ),
                    const SizedBox(height: 12),
                    Stack(
                      clipBehavior: Clip.none,
                      children: [
                        Container(
                          padding: const EdgeInsets.all(3),
                          decoration: const BoxDecoration(
                              color: Colors.white, shape: BoxShape.circle),
                          child: AvatarView(
                              name: profile.fullName,
                              path: profile.avatarPath,
                              radius: 44),
                        ),
                        Positioned(
                          right: 0,
                          bottom: 2,
                          child: GestureDetector(
                            onTap: () => context.push('/profile/edit'),
                            child: Container(
                              padding: const EdgeInsets.all(6),
                              decoration: BoxDecoration(
                                  color: primary,
                                  shape: BoxShape.circle,
                                  border: Border.all(
                                      color: Colors.white, width: 2)),
                              child: const Icon(Icons.edit_rounded,
                                  size: 14, color: Colors.white),
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Text(profile.fullName,
                        style: theme.textTheme.headlineMedium
                            ?.copyWith(color: onHeader),
                        textAlign: TextAlign.center),
                    if (contact.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(contact,
                          style: theme.textTheme.bodySmall?.copyWith(
                              color: onHeader.withValues(alpha: 0.9)),
                          textAlign: TextAlign.center),
                    ],
                    const SizedBox(height: 16),
                    FilledButton.icon(
                      style: FilledButton.styleFrom(
                        backgroundColor: Colors.white,
                        foregroundColor: primary,
                        minimumSize: const Size(190, 46),
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(24)),
                      ),
                      onPressed: () => context.push('/profile/edit'),
                      icon: const Icon(Icons.edit_outlined, size: 18),
                      label: const Text('Edit profile'),
                    ),
                  ],
                ),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(Gap.page, 12, Gap.page, 32),
            child: Column(
              children: [
                _Tile(
                    icon: Icons.favorite_border_rounded,
                    label: 'My favorites',
                    onTap: () => context.go('/favorites')),
                _Tile(
                    icon: Icons.calendar_month_outlined,
                    label: 'My bookings',
                    onTap: () => context.go('/bookings')),
                _Tile(
                    icon: Icons.receipt_long_outlined,
                    label: 'Payment history',
                    onTap: () => context.push('/payments')),
                _Tile(
                  icon: Icons.place_outlined,
                  label: 'City',
                  value: city?.name ?? 'Not selected',
                  onTap: () => showCitySheet(context),
                ),
                _Tile(
                    icon: Icons.notifications_none_rounded,
                    label: 'Notifications',
                    onTap: () => context.push('/notifications')),
                _Tile(
                    icon: Icons.settings_outlined,
                    label: 'Settings',
                    onTap: () => context.push('/settings')),
                const SizedBox(height: 8),
                _Tile(
                  icon: Icons.logout_rounded,
                  label: 'Sign out',
                  destructive: true,
                  onTap: () => _confirmSignOut(context, ref),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _confirmSignOut(BuildContext context, WidgetRef ref) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Sign out?'),
        content:
            const Text('You will need to sign in again to see your favorites.'),
        actions: [
          TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(false),
              child: const Text('Cancel')),
          TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(true),
              child: const Text('Sign out')),
        ],
      ),
    );
    if (ok == true) await ref.read(authControllerProvider.notifier).signOut();
  }
}

class _Tile extends StatelessWidget {
  const _Tile(
      {required this.icon,
      required this.label,
      required this.onTap,
      this.value,
      this.destructive = false});

  final IconData icon;
  final String label;
  final String? value;
  final bool destructive;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final color = destructive ? ZuruvColors.error : theme.colorScheme.onSurface;
    return Column(
      children: [
        ListTile(
          contentPadding: const EdgeInsets.symmetric(horizontal: 4),
          leading: Icon(icon,
              color: destructive ? color : theme.colorScheme.primary),
          title: Text(label,
              style: TextStyle(color: color, fontWeight: FontWeight.w500)),
          trailing: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (value != null) Text(value!, style: theme.textTheme.bodySmall),
              if (!destructive)
                Icon(Icons.chevron_right_rounded,
                    color: theme.colorScheme.onSurfaceVariant),
            ],
          ),
          onTap: onTap,
        ),
        if (!destructive) Divider(height: 1, color: theme.colorScheme.outline),
      ],
    );
  }
}
