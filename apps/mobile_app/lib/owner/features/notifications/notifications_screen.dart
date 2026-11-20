import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';

import 'package:zuruv/core/network/api_helpers.dart';
import 'package:zuruv/owner/core/utils/format.dart';
import 'package:zuruv/owner/shared/models/models.dart';
import 'package:zuruv/owner/shared/repositories/owner_repository.dart';
import 'package:zuruv/owner/shared/widgets/common_widgets.dart';

IconData iconForNotification(String type) {
  if (type.startsWith('booking.')) return Icons.event_available_rounded;
  if (type.startsWith('payment.')) return Icons.payments_rounded;
  if (type.startsWith('payout.')) return Icons.account_balance_rounded;
  if (type.startsWith('review.')) return Icons.star_rounded;
  return Icons.notifications_rounded;
}

/// Groups shown as filter chips; the value is sent as `group`.
const notificationGroups = [('All', 'all'), ('Bookings', 'bookings'), ('Payments', 'payments'), ('Reviews', 'reviews')];

final notificationGroupProvider = StateProvider.autoDispose<String>((ref) => 'all');

final notificationsProvider = FutureProvider.autoDispose<NotificationPage>((ref) {
  final group = ref.watch(notificationGroupProvider);
  return ref.watch(ownerRepositoryProvider).notifications(group: group);
});

/// Unread badge for the dashboard bell. Quietly 0 while loading or on error.
final unreadCountProvider = Provider.autoDispose<int>((ref) {
  return ref.watch(_unreadAllProvider).valueOrNull?.unreadCount ?? 0;
});

final _unreadAllProvider = FutureProvider.autoDispose<NotificationPage>(
  (ref) => ref.watch(ownerRepositoryProvider).notifications(unreadOnly: true),
);

class NotificationsScreen extends ConsumerWidget {
  const NotificationsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final group = ref.watch(notificationGroupProvider);
    final page = ref.watch(notificationsProvider);

    Future<void> markAll() async {
      try {
        await ref.read(ownerRepositoryProvider).markAllRead();
        ref.invalidate(notificationsProvider);
        ref.invalidate(_unreadAllProvider);
      } catch (e) {
        if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(errorMessage(e))));
      }
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Notifications'),
        actions: [
          if ((page.valueOrNull?.unreadCount ?? 0) > 0) TextButton(onPressed: markAll, child: const Text('Mark all read')),
        ],
      ),
      body: ResponsivePage(
        maxWidth: 720,
        child: Column(
          children: [
            SizedBox(
              height: 52,
              child: ListView(
                scrollDirection: Axis.horizontal,
                children: [
                  for (final (label, value) in notificationGroups)
                    Padding(
                      padding: const EdgeInsets.only(right: 8, top: 8, bottom: 8),
                      child: ChoiceChip(
                        label: Text(label),
                        selected: group == value,
                        onSelected: (_) => ref.read(notificationGroupProvider.notifier).state = value,
                      ),
                    ),
                ],
              ),
            ),
            Expanded(
              child: page.when(
                loading: () => const LoadingView(),
                error: (e, _) => ErrorView.fromError(e, onRetry: () => ref.invalidate(notificationsProvider)),
                data: (p) => p.items.isEmpty
                    ? const EmptyState(
                        icon: Icons.notifications_none_rounded,
                        title: 'No notifications',
                        message: 'New bookings, payments, cancellations and reviews will appear here.',
                      )
                    : RefreshIndicator(
                        onRefresh: () async => ref.invalidate(notificationsProvider),
                        child: ListView.separated(
                          itemCount: p.items.length,
                          separatorBuilder: (_, __) => const Divider(height: 1),
                          itemBuilder: (context, i) => _Tile(n: p.items[i]),
                        ),
                      ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Tile extends ConsumerWidget {
  const _Tile({required this.n});
  final OwnerNotification n;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return ListTile(
      contentPadding: const EdgeInsets.symmetric(vertical: 4),
      leading: CircleAvatar(
        backgroundColor: Theme.of(context).colorScheme.primaryContainer,
        child: Icon(iconForNotification(n.type), color: Theme.of(context).colorScheme.primary, size: 20),
      ),
      title: Text(n.title, style: TextStyle(fontWeight: n.isRead ? FontWeight.w500 : FontWeight.w800)),
      subtitle: Text([if (n.body != null) n.body!, timeAgo(n.createdAt)].join('\n')),
      isThreeLine: n.body != null,
      trailing: n.isRead ? null : Container(width: 10, height: 10, decoration: BoxDecoration(color: Theme.of(context).colorScheme.primary, shape: BoxShape.circle)),
      onTap: n.isRead
          ? null
          : () async {
              try {
                await ref.read(ownerRepositoryProvider).markRead(n.id);
                ref.invalidate(notificationsProvider);
                ref.invalidate(_unreadAllProvider);
              } catch (e) {
                if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(errorMessage(e))));
              }
            },
    );
  }
}
