import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';

import '../../shared/repositories/owner_repository.dart';

final notificationChannelsProvider = FutureProvider.autoDispose<NotificationChannels>(
  (ref) => ref.watch(ownerRepositoryProvider).notificationChannels(),
);

/// How the owner wants to be told about bookings, payments and reviews. Both switches are stored
/// on the server (the same account is used on every device) and decide whether a push or an
/// e-mail is sent. In-app notifications are always kept.
class NotificationPrefsScreen extends ConsumerStatefulWidget {
  const NotificationPrefsScreen({super.key});

  @override
  ConsumerState<NotificationPrefsScreen> createState() => _NotificationPrefsScreenState();
}

class _NotificationPrefsScreenState extends ConsumerState<NotificationPrefsScreen> {
  bool _saving = false;

  Future<void> _save({bool? push, bool? email}) async {
    setState(() => _saving = true);
    try {
      await ref.read(ownerRepositoryProvider).setNotificationChannels(push: push, email: email);
      ref.invalidate(notificationChannelsProvider);
    } catch (e) {
      if (mounted) {
        final message = e is ApiException ? e.message : 'Could not save your choice. Please try again.';
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final channels = ref.watch(notificationChannelsProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Notification preferences')),
      body: ResponsivePage(
        maxWidth: 640,
        child: channels.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => ErrorView.fromError(e, onRetry: () => ref.invalidate(notificationChannelsProvider)),
          data: (c) => ListView(
            padding: const EdgeInsets.symmetric(vertical: 12),
            children: [
              SwitchListTile(
                title: const Text('Push notifications'),
                subtitle: const Text('New and cancelled bookings, payments received, reviews'),
                value: c.push,
                onChanged: _saving ? null : (v) => _save(push: v),
              ),
              SwitchListTile(
                title: const Text('E-mail'),
                subtitle: const Text('Booking and payment e-mails'),
                value: c.email,
                onChanged: _saving ? null : (v) => _save(email: v),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
