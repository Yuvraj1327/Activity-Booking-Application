import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';

import '../../core/storage/preferences.dart';
import '../../shared/widgets/common_widgets.dart';

/// Which kinds of alerts the owner wants. Stored on this device only: push notifications are
/// built in Step 7, and there is no server-side preference yet.
class NotificationPrefsController extends Notifier<Map<String, bool>> {
  @override
  Map<String, bool> build() {
    final p = ref.read(sharedPreferencesProvider);
    return {
      for (final k in const [OwnerPrefKeys.notifyBookings, OwnerPrefKeys.notifyPayments, OwnerPrefKeys.notifyReviews])
        k: p.getBool(k) ?? true,
    };
  }

  Future<void> set(String key, bool value) async {
    state = {...state, key: value};
    await ref.read(sharedPreferencesProvider).setBool(key, value);
  }
}

final notificationPrefsProvider = NotifierProvider<NotificationPrefsController, Map<String, bool>>(NotificationPrefsController.new);

class NotificationPrefsScreen extends ConsumerWidget {
  const NotificationPrefsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final prefs = ref.watch(notificationPrefsProvider);
    final c = ref.read(notificationPrefsProvider.notifier);
    return Scaffold(
      appBar: AppBar(title: const Text('Notification preferences')),
      body: ResponsivePage(
        maxWidth: 640,
        child: ListView(
          padding: const EdgeInsets.symmetric(vertical: 12),
          children: [
            SwitchListTile(
              title: const Text('Bookings'),
              subtitle: const Text('New and cancelled bookings'),
              value: prefs[OwnerPrefKeys.notifyBookings] ?? true,
              onChanged: (v) => c.set(OwnerPrefKeys.notifyBookings, v),
            ),
            SwitchListTile(
              title: const Text('Payments & payouts'),
              subtitle: const Text('Payments received and payout updates'),
              value: prefs[OwnerPrefKeys.notifyPayments] ?? true,
              onChanged: (v) => c.set(OwnerPrefKeys.notifyPayments, v),
            ),
            SwitchListTile(
              title: const Text('Reviews'),
              subtitle: const Text('New reviews on your venues'),
              value: prefs[OwnerPrefKeys.notifyReviews] ?? true,
              onChanged: (v) => c.set(OwnerPrefKeys.notifyReviews, v),
            ),
            const Padding(
              padding: EdgeInsets.all(16),
              child: UnavailableCard(
                title: 'Saved on this device',
                message: 'Push notifications are not switched on yet. These choices will apply when they are.',
                icon: Icons.phone_android_rounded,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
