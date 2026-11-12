import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:go_router/go_router.dart';

import '../../core/constants/tokens.dart';
import '../../core/network/api_helpers.dart';
import '../../core/utils/dates.dart';
import '../../shared/models/app_notification.dart';
import '../../shared/repositories/notification_repository.dart';
import '../../shared/widgets/common_widgets.dart';

final notificationsProvider = FutureProvider.autoDispose<NotificationPageData>((ref) {
  return ref.watch(notificationRepositoryProvider).list();
});

/// Badge count. Refreshed when the screen opens and when a push arrives in the foreground.
final unreadCountProvider = FutureProvider.autoDispose<int>((ref) {
  return ref.watch(notificationRepositoryProvider).unreadCount();
});

class NotificationsScreen extends ConsumerWidget {
  const NotificationsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final list = ref.watch(notificationsProvider);
    Future<void> markAll() async {
      try {
        await ref.read(notificationRepositoryProvider).markAllRead();
      } catch (_) {}
      ref.invalidate(notificationsProvider);
      ref.invalidate(unreadCountProvider);
    }

    return Scaffold(
      appBar: AppBar(
        leading: IconButton(onPressed: () => context.pop(), icon: const Icon(Icons.arrow_back_rounded)),
        title: Text('Notifications', style: Theme.of(context).textTheme.titleLarge),
        actions: [
          if ((list.valueOrNull?.unreadCount ?? 0) > 0) TextButton(onPressed: markAll, child: const Text('Mark all read')),
        ],
      ),
      body: list.when(
        loading: () => const LoadingView(),
        error: (e, _) => ErrorView(message: errorMessage(e), onRetry: () => ref.invalidate(notificationsProvider)),
        data: (page) {
          if (page.items.isEmpty) {
            return const EmptyState(
              icon: Icons.notifications_none_rounded,
              title: 'Nothing here yet',
              message: 'Booking confirmations and payment updates will show up here.',
            );
          }
          return RefreshIndicator(
            onRefresh: () async => ref.invalidate(notificationsProvider),
            child: ListView.separated(
              itemCount: page.items.length,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (context, i) => _Tile(item: page.items[i]),
            ),
          );
        },
      ),
    );
  }
}

class _Tile extends ConsumerWidget {
  const _Tile({required this.item});

  final AppNotification item;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    return ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: Gap.page, vertical: 6),
      leading: Icon(
        item.type.startsWith('payment') ? Icons.payments_outlined : Icons.event_available_outlined,
        color: item.isRead ? ZuruvColors.textSecondary : theme.colorScheme.primary,
      ),
      title: Text(item.title, style: theme.textTheme.titleSmall?.copyWith(fontWeight: item.isRead ? FontWeight.w500 : FontWeight.w700)),
      subtitle: Text([if (item.body != null) item.body!, clockTime(item.createdAt.toLocal())].join('\n')),
      isThreeLine: item.body != null,
      trailing: item.isRead ? null : Icon(Icons.circle, size: 10, color: theme.colorScheme.primary),
      onTap: () async {
        if (!item.isRead) {
          try {
            await ref.read(notificationRepositoryProvider).markRead(item.id);
          } catch (_) {}
          ref.invalidate(notificationsProvider);
          ref.invalidate(unreadCountProvider);
        }
        if (item.bookingId != null && context.mounted) context.push('/bookings/${item.bookingId}');
      },
    );
  }
}
