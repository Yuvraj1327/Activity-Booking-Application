import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:go_router/go_router.dart';

import '../../core/constants/tokens.dart';
import '../../shared/models/models.dart';
import '../../shared/repositories/owner_repository.dart';
import 'avatar_view.dart';

final businessProvider = FutureProvider.autoDispose<OwnerBusiness>((ref) => ref.watch(ownerRepositoryProvider).business());

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  Future<void> _logout(BuildContext context, WidgetRef ref) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Log out?'),
        content: const Text('You will need to sign in again to manage your venues.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Log out')),
        ],
      ),
    );
    if (ok == true) await ref.read(authControllerProvider.notifier).signOut();
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authControllerProvider);
    final profile = auth is Authenticated ? auth.profile : null;
    final business = ref.watch(businessProvider).valueOrNull;
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(title: const Text('Profile')),
      body: ResponsivePage(
        maxWidth: 640,
        child: ListView(
          padding: const EdgeInsets.only(bottom: 32, top: 8),
          children: [
            Row(children: [
              AvatarView(name: profile?.fullName ?? '', path: profile?.avatarPath, radius: 34),
              const SizedBox(width: Gap.lg),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(profile?.fullName ?? '', style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
                  if (business != null && business.businessName.isNotEmpty) Text(business.businessName, style: const TextStyle(color: ZuruvColors.textSecondary)),
                  if (profile?.email != null) Text(profile!.email!, style: theme.textTheme.bodySmall?.copyWith(color: ZuruvColors.textSecondary)),
                ]),
              ),
              IconButton(tooltip: 'Edit profile', onPressed: () => context.push('/profile/edit'), icon: const Icon(Icons.edit_rounded)),
            ]),
            const SizedBox(height: Gap.lg),
            _Group(title: 'Business', tiles: [
              _Tile(Icons.business_rounded, 'Business information', 'Name, phone, e-mail, address', '/profile/business'),
              _Tile(Icons.account_balance_rounded, 'Bank & payout settings', 'Set up where payouts go', '/profile/payout'),
            ]),
            _Group(title: 'Insights', tiles: [
              _Tile(Icons.insights_rounded, 'Analytics', 'Performance by date range', '/analytics'),
              _Tile(Icons.star_rounded, 'Reviews', 'What customers say', '/reviews'),
              _Tile(Icons.notifications_none_rounded, 'Notifications', 'Bookings, payments, reviews', '/notifications'),
            ]),
            _Group(title: 'Settings', tiles: [
              _Tile(Icons.tune_rounded, 'Notification preferences', 'Choose what you hear about', '/profile/notifications'),
              _Tile(Icons.help_outline_rounded, 'Help & support', null, '/profile/help'),
              _Tile(Icons.description_outlined, 'Terms & policies', null, '/profile/terms'),
            ]),
            const SizedBox(height: Gap.lg),
            OutlinedButton.icon(
              onPressed: () => _logout(context, ref),
              style: OutlinedButton.styleFrom(foregroundColor: ZuruvColors.error),
              icon: const Icon(Icons.logout_rounded),
              label: const Text('Log out'),
            ),
          ],
        ),
      ),
    );
  }
}

class _Tile {
  const _Tile(this.icon, this.title, this.subtitle, this.route);
  final IconData icon;
  final String title;
  final String? subtitle;
  final String route;
}

class _Group extends StatelessWidget {
  const _Group({required this.title, required this.tiles});
  final String title;
  final List<_Tile> tiles;

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Padding(
        padding: const EdgeInsets.only(top: Gap.lg, bottom: Gap.sm),
        child: Text(title, style: Theme.of(context).textTheme.labelLarge?.copyWith(color: ZuruvColors.textSecondary)),
      ),
      Card(
        margin: EdgeInsets.zero,
        child: Column(children: [
          for (var i = 0; i < tiles.length; i++) ...[
            if (i > 0) const Divider(height: 1),
            ListTile(
              leading: Icon(tiles[i].icon, color: Theme.of(context).colorScheme.primary),
              title: Text(tiles[i].title),
              subtitle: tiles[i].subtitle == null ? null : Text(tiles[i].subtitle!),
              trailing: const Icon(Icons.chevron_right_rounded),
              onTap: () => context.push(tiles[i].route),
            ),
          ],
        ]),
      ),
    ]);
  }
}
