import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../shared/widgets/common_widgets.dart';

/// Placeholder tab: the booking flow and history are built in a later step.
class BookingsScreen extends StatelessWidget {
  const BookingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('My Bookings', style: Theme.of(context).textTheme.titleLarge)),
      body: EmptyState(
        icon: Icons.calendar_month_outlined,
        title: 'No bookings yet',
        message: 'Booking is coming soon. Your upcoming and past bookings will appear here.',
        action: OutlinedButton(
          style: OutlinedButton.styleFrom(minimumSize: const Size(180, 48)),
          onPressed: () => context.go('/explore'),
          child: const Text('Explore venues'),
        ),
      ),
    );
  }
}
