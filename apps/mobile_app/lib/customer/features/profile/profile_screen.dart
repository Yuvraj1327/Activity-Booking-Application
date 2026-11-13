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
    final contact = [profile.email, profile.phone].whereType<String>().where((e) => e.isNotEmpty).join('  ·  ');

    return Scaffold(
      appBar: AppBar(title: Text('Profile', style: theme.textTheme.titleLarge)),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(Gap.page, 8, Gap.page, 32),
        children: [
          Center(child: AvatarView(name: profile.fullName, path: profile.avatarPath, radius: 44)),
          const SizedBox(height: 14),
          Text(profile.fullName, style: theme.textTheme.headlineMedium, textAlign: TextAlign.center),
          if (contact.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(contact, style: theme.textTheme.bodySmall, textAlign: TextAlign.center),
          ],
          const SizedBox(height: 20),
          Center(
            child: OutlinedButton.icon(
              style: OutlinedButton.styleFrom(minimumSize: const Size(180, 44)),
              onPressed: () => context.push('/profile/edit'),
              icon: const Icon(Icons.edit_outlined, size: 18),
              label: const Text('Edit profile'),
            ),
          ),
          const SizedBox(height: 24),
          const Divider(),
          _Tile(icon: Icons.favorite_border_rounded, label: 'My favorites', onTap: () => context.go('/favorites')),
          _Tile(icon: Icons.calendar_month_outlined, label: 'My bookings', onTap: () => context.go('/bookings')),
          _Tile(icon: Icons.receipt_long_outlined, label: 'Payment history', onTap: () => context.push('/payments')),
          _Tile(
            icon: Icons.place_outlined,
            label: 'City',
            value: city?.name ?? 'Not selected',
            onTap: () => showCitySheet(context),
          ),
          _Tile(icon: Icons.notifications_none_rounded, label: 'Notifications', onTap: () => context.push('/notifications')),
          const Divider(),
          _Tile(
            icon: Icons.logout_rounded,
            label: 'Sign out',
            destructive: true,
            onTap: () => _confirmSignOut(context, ref),
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
        content: const Text('You will need to sign in again to see your favorites.'),
        actions: [
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(false), child: const Text('Cancel')),
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(true), child: const Text('Sign out')),
        ],
      ),
    );
    if (ok == true) await ref.read(authControllerProvider.notifier).signOut();
  }
}

class _Tile extends StatelessWidget {
  const _Tile({required this.icon, required this.label, required this.onTap, this.value, this.destructive = false});

  final IconData icon;
  final String label;
  final String? value;
  final bool destructive;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = destructive ? ZuruvColors.error : ZuruvColors.text;
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: Icon(icon, color: destructive ? color : Theme.of(context).colorScheme.primary),
      title: Text(label, style: TextStyle(color: color, fontWeight: FontWeight.w500)),
      trailing: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (value != null) Text(value!, style: Theme.of(context).textTheme.bodySmall),
          if (!destructive) const Icon(Icons.chevron_right_rounded, color: ZuruvColors.textSecondary),
        ],
      ),
      onTap: onTap,
    );
  }
}
