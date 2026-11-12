import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../shared/widgets/common_widgets.dart';

/// Placeholder: the notifications API and push delivery arrive with booking.
class NotificationsScreen extends StatelessWidget {
  const NotificationsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        leading: IconButton(onPressed: () => context.pop(), icon: const Icon(Icons.arrow_back_rounded)),
        title: Text('Notifications', style: Theme.of(context).textTheme.titleLarge),
      ),
      body: const EmptyState(
        icon: Icons.notifications_none_rounded,
        title: 'Nothing here yet',
        message: 'Booking confirmations and reminders will show up here.',
      ),
    );
  }
}
