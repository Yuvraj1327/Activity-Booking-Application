import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:go_router/go_router.dart';

import 'package:zuruv/core/constants/tokens.dart';
import 'package:zuruv/owner/shared/models/models.dart';
import 'package:zuruv/owner/shared/widgets/common_widgets.dart';
import 'package:zuruv/owner/shared/repositories/owner_repository.dart';
import 'package:zuruv/owner/features/profile/avatar_view.dart';

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

    final phone = (profile?.phone ?? '').trim();
    return Scaffold(
      appBar: AppBar(title: const Text('Profile'), titleSpacing: Gap.page),
      body: ResponsivePage(
        maxWidth: 640,
        child: ListView(
          padding: const EdgeInsets.only(bottom: 32, top: 4),
          children: [
            OwnerCard(
              padding: const EdgeInsets.all(Gap.lg),
              onTap: () => context.push('/owner/profile/edit'),
              child: Row(children: [
                AvatarView(name: profile?.fullName ?? '', path: profile?.avatarPath, radius: 36),
                const SizedBox(width: Gap.lg),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(profile?.fullName ?? '', maxLines: 1, overflow: TextOverflow.ellipsis, style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
                    Text(
                      business != null && business.businessName.isNotEmpty ? business.businessName : 'Owner',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(color: ZuruvColors.textSecondary, fontWeight: FontWeight.w500),
                    ),
                    const SizedBox(height: 6),
                    if (profile?.email != null) _Contact(Icons.mail_outline_rounded, profile!.email!),
                    if (phone.isNotEmpty) _Contact(Icons.phone_outlined, phone),
                  ]),
                ),
                const SizedBox(width: Gap.sm),
                IconButton.filledTonal(tooltip: 'Edit profile', onPressed: () => context.push('/owner/profile/edit'), icon: const Icon(Icons.edit_rounded, size: 20)),
              ]),
            ),
            const _Group(title: 'Business', tiles: [
              _Tile(Icons.business_rounded, 'Business information', 'Name, phone, address, GST (optional)', '/owner/profile/business'),
              _Tile(Icons.account_balance_rounded, 'Bank & payout settings', 'Set up where payouts go', '/owner/profile/payout'),
            ]),
            const _Group(title: 'Insights', tiles: [
              _Tile(Icons.insights_rounded, 'Analytics', 'Performance & reports', '/owner/analytics'),
              _Tile(Icons.star_rounded, 'Reviews', 'What customers say', '/owner/reviews'),
              _Tile(Icons.notifications_none_rounded, 'Notifications', 'Bookings, payments, reviews', '/owner/notifications'),
            ]),
            const _Group(title: 'App', tiles: [
              _Tile(Icons.settings_outlined, 'Settings', 'Account, appearance, help', '/owner/settings'),
            ]),
            const SizedBox(height: Gap.xl),
            OutlinedButton.icon(
              onPressed: () => _logout(context, ref),
              style: OutlinedButton.styleFrom(
                foregroundColor: ZuruvColors.error,
                minimumSize: const Size.fromHeight(52),
                side: BorderSide(color: ZuruvColors.error.withValues(alpha: 0.35)),
                backgroundColor: Theme.of(context).colorScheme.surface,
              ),
              icon: const Icon(Icons.logout_rounded),
              label: const Text('Log out', style: TextStyle(fontWeight: FontWeight.w700)),
            ),
          ],
        ),
      ),
    );
  }
}

class _Contact extends StatelessWidget {
  const _Contact(this.icon, this.text);
  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(top: 2),
        child: Row(children: [
          Icon(icon, size: 15, color: Theme.of(context).colorScheme.primary),
          const SizedBox(width: 6),
          Expanded(child: Text(text, maxLines: 1, overflow: TextOverflow.ellipsis, style: Theme.of(context).textTheme.bodySmall?.copyWith(color: ZuruvColors.textSecondary))),
        ]),
      );
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
    final theme = Theme.of(context);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Padding(
        padding: const EdgeInsets.only(top: Gap.xl, bottom: Gap.sm, left: 2),
        child: Text(title, style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
      ),
      OwnerCard(
        padding: EdgeInsets.zero,
        child: Column(children: [
          for (var i = 0; i < tiles.length; i++) ...[
            if (i > 0) Divider(height: 1, indent: 68, color: theme.colorScheme.outline.withValues(alpha: 0.5)),
            InkWell(
              borderRadius: BorderRadius.circular(Radii.card),
              onTap: () => context.push(tiles[i].route),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: Gap.lg, vertical: Gap.md),
                child: Row(children: [
                  IconBadge(tiles[i].icon, size: 40),
                  const SizedBox(width: Gap.md),
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(tiles[i].title, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
                      if (tiles[i].subtitle != null)
                        Text(tiles[i].subtitle!, style: theme.textTheme.bodySmall?.copyWith(color: ZuruvColors.textSecondary)),
                    ]),
                  ),
                  const Icon(Icons.chevron_right_rounded, color: ZuruvColors.textSecondary),
                ]),
              ),
            ),
          ],
        ]),
      ),
    ]);
  }
}
