import 'package:flutter/material.dart';
import 'package:flutter_shared/flutter_shared.dart';

import '../../core/constants/tokens.dart';

class _InfoPage extends StatelessWidget {
  const _InfoPage({required this.title, required this.sections});
  final String title;
  final List<(String, String)> sections;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: ResponsivePage(
        maxWidth: 640,
        child: ListView(
          padding: const EdgeInsets.symmetric(vertical: 16),
          children: [
            for (final (head, body) in sections) ...[
              Text(head, style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
              const SizedBox(height: 6),
              Text(body, style: theme.textTheme.bodyMedium?.copyWith(color: ZuruvColors.textSecondary)),
              const SizedBox(height: Gap.xl),
            ],
          ],
        ),
      ),
    );
  }
}

/// Placeholder content. A support contact has not been supplied, so none is shown; it is added
/// here once the business provides one.
class HelpScreen extends StatelessWidget {
  const HelpScreen({super.key});
  @override
  Widget build(BuildContext context) => const _InfoPage(title: 'Help & support', sections: [
        ('Publishing a venue', 'A venue goes live once it has a city, a location on the map and at least one sport. Save it as a draft until you are ready.'),
        ('Opening hours', 'Set weekly hours and special dates from a venue\'s Manage slots page. Online booking is not switched on yet.'),
        ('Contact support', 'Support contact details will be added here before launch.'),
      ]);
}

/// Placeholder content. Final legal text is pending (open question on legal pages).
class TermsScreen extends StatelessWidget {
  const TermsScreen({super.key});
  @override
  Widget build(BuildContext context) => const _InfoPage(title: 'Terms & policies', sections: [
        ('Terms of service', 'The final terms for venue owners are pending legal review and will be published here.'),
        ('Privacy policy', 'The privacy policy is pending legal review and will be published here.'),
      ]);
}
