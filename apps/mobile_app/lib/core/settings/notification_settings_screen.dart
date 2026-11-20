import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';

import 'package:zuruv/core/network/api_helpers.dart';
import 'package:zuruv/core/settings/settings_repository.dart';
import 'package:zuruv/core/settings/settings_widgets.dart';

final notificationPrefsProvider = FutureProvider.autoDispose<NotificationPrefs>(
  (ref) => ref.watch(settingsRepositoryProvider).notificationPrefs(),
);

/// Push / e-mail master switches plus booking, payment and promotional switches. They are stored
/// on the account, so they apply on every device, and the server checks them before it sends
/// anything. The in-app notification list is always kept.
class NotificationSettingsScreen extends ConsumerStatefulWidget {
  const NotificationSettingsScreen({super.key});

  @override
  ConsumerState<NotificationSettingsScreen> createState() => _NotificationSettingsScreenState();
}

class _NotificationSettingsScreenState extends ConsumerState<NotificationSettingsScreen> {
  bool _saving = false;

  Future<void> _set(String field, bool value) async {
    setState(() => _saving = true);
    try {
      await ref.read(settingsRepositoryProvider).setNotificationPrefs({field: value});
      ref.invalidate(notificationPrefsProvider);
      await ref.read(notificationPrefsProvider.future);
    } catch (e) {
      if (mounted) showSnack(context, errorMessage(e));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final prefs = ref.watch(notificationPrefsProvider);
    return prefs.when(
      loading: () => const Scaffold(body: LoadingView()),
      error: (e, _) => Scaffold(
        appBar: AppBar(title: const Text('Notifications')),
        body: ErrorView.fromError(e, onRetry: () => ref.invalidate(notificationPrefsProvider)),
      ),
      data: (p) {
        Widget sw(String title, String subtitle, bool value, String field) => SwitchListTile(
              title: Text(title),
              subtitle: Text(subtitle),
              value: value,
              onChanged: _saving ? null : (v) => _set(field, v),
            );
        return SettingsPage(
          title: 'Notifications',
          children: [
            if (_saving) const Padding(padding: EdgeInsets.only(top: 4), child: LinearProgressIndicator()),
            SettingsGroup(title: 'How to reach me', children: [
              sw('Push notifications', 'Alerts on this and your other phones', p.push, 'push_enabled'),
              sw('E-mail', 'Booking and payment e-mails', p.email, 'email_enabled'),
            ]),
            SettingsGroup(
              title: 'What to tell me about',
              footer: 'Turned-off topics are still listed in the in-app notification centre; they just don\'t push or e-mail you.',
              children: [
                sw('Bookings', 'New, confirmed and cancelled bookings', p.booking, 'booking_enabled'),
                sw('Payments', 'Payments received, failed or refunded', p.payment, 'payment_enabled'),
                sw('Offers & promotions', 'News and offers from ZURUV', p.promo, 'promo_enabled'),
              ],
            ),
          ],
        );
      },
    );
  }
}
