import 'package:flutter/material.dart';
import 'package:flutter_shared/flutter_shared.dart';

import '../../shared/widgets/common_widgets.dart';

/// Bank & payout settings.
///
/// How payouts work (schedule, fees, where bank details are stored and who may see them) is an
/// open business decision (Q10), so this screen deliberately collects nothing: no form fields and
/// no buttons that would pretend to save. Earnings that are real today (gross captured payments)
/// are on the Payments screen.
class PayoutSettingsScreen extends StatelessWidget {
  const PayoutSettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Bank & payout settings')),
      body: SafeArea(
        child: ResponsivePage(
          maxWidth: 480,
          child: ListView(
            padding: const EdgeInsets.symmetric(vertical: 16),
            children: const [
              UnavailableCard(
                title: 'Not available yet',
                message:
                    'Payouts start once the payout rules are approved. Bank details will be collected here, with secure storage, at that point. Nothing is stored on your device or on the server today.',
                icon: Icons.lock_outline_rounded,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
