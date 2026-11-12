import 'package:flutter/material.dart';
import 'package:flutter_shared/flutter_shared.dart';

import '../../core/constants/tokens.dart';
import '../../shared/widgets/common_widgets.dart';

/// Bank & payout settings: UI foundation only.
///
/// Where bank details are stored, how they are encrypted and who may see them are still open
/// decisions (payout rules are decided with Step 7). Until then this screen collects nothing: the
/// fields are shown disabled and no value is read, sent or stored on the device or the server.
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
            children: [
              const UnavailableCard(
                title: 'Not available yet',
                message:
                    'Payouts start with online payments. Bank details will be collected here once secure storage and payout rules are approved. Nothing you type is saved today.',
                icon: Icons.lock_outline_rounded,
              ),
              const SizedBox(height: Gap.xl),
              const TextField(enabled: false, decoration: InputDecoration(labelText: 'Account holder name')),
              const SizedBox(height: Gap.lg),
              const TextField(enabled: false, obscureText: true, decoration: InputDecoration(labelText: 'Account number')),
              const SizedBox(height: Gap.lg),
              const TextField(enabled: false, decoration: InputDecoration(labelText: 'IFSC code')),
              const SizedBox(height: Gap.lg),
              const TextField(enabled: false, decoration: InputDecoration(labelText: 'Bank name')),
              const SizedBox(height: 28),
              const FilledButton(onPressed: null, child: Text('Save bank details')),
            ],
          ),
        ),
      ),
    );
  }
}
