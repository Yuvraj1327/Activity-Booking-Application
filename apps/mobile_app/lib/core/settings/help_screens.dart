import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:go_router/go_router.dart';
import 'package:package_info_plus/package_info_plus.dart';

import 'package:zuruv/core/constants/tokens.dart';
import 'package:zuruv/core/network/api_helpers.dart';
import 'package:zuruv/core/settings/app_settings.dart';
import 'package:zuruv/core/settings/settings_repository.dart';
import 'package:zuruv/core/settings/settings_widgets.dart';

typedef Faq = (String, String);

const customerFaqs = <Faq>[
  ('How do I book a venue?', 'Open a venue, choose a sport, court and time slot, then confirm and pay. Your booking appears under Bookings.'),
  ('Can I cancel a booking?', 'Open the booking from the Bookings tab and tap Cancel. Refunds follow the venue\'s cancellation rules shown on the booking.'),
  ('My payment failed or was charged twice', 'Failed payments are not charged. If money left your account and the booking is not confirmed, send us an issue report with the booking code and we will check it.'),
  ('How do I change my city?', 'Go to Settings > Preferences > City, or tap the city on the Home screen.'),
];

const ownerFaqs = <Faq>[
  ('When does my venue go live?', 'A venue is published once it has a city, a location on the map and at least one sport. Save it as a draft until you are ready.'),
  ('How do I set opening hours?', 'Open a venue and choose Manage slots to set weekly hours and special dates.'),
  ('Where do I see my earnings?', 'The Earnings tab shows payments received for your bookings; Analytics shows performance by date range.'),
  ('A customer cancelled. What happens?', 'The slot is freed automatically and you receive a notification. Turn notifications on or off under Settings > Notifications.'),
];

/// FAQs published in the admin console. Empty (or unreachable) means the built-in list below is shown.
final cmsFaqsProvider = FutureProvider.autoDispose.family<List<Faq>, bool>((ref, isOwner) async {
  try {
    final items = await ref.watch(settingsRepositoryProvider).contentList(kind: 'faq', audience: isOwner ? 'owner' : 'customer');
    return [for (final i in items) (i['title'] as String, i['body'] as String)];
  } catch (_) {
    return const <Faq>[];
  }
});

/// FAQs plus entry points to contact support, send feedback and report an issue.
class HelpScreen extends ConsumerWidget {
  const HelpScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final base = ref.watch(settingsBaseProvider);
    final isOwner = ref.watch(isOwnerProvider);
    final managed = ref.watch(cmsFaqsProvider(isOwner)).valueOrNull ?? const <Faq>[];
    final faqs = managed.isNotEmpty ? managed : (isOwner ? ownerFaqs : customerFaqs);
    return SettingsPage(
      title: 'Help & support',
      children: [
        SettingsGroup(title: 'Frequently asked questions', children: [
          for (final (q, a) in faqs)
            ExpansionTile(
              shape: const Border(),
              collapsedShape: const Border(),
              title: Text(q, style: const TextStyle(fontWeight: FontWeight.w600)),
              childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
              expandedCrossAxisAlignment: CrossAxisAlignment.start,
              children: [Text(a)],
            ),
        ]),
        SettingsGroup(title: 'Talk to us', children: [
          SettingsTile(icon: Icons.support_agent_rounded, title: 'Contact support', subtitle: 'Ask for help with your account', onTap: () => context.push('$base/help/support')),
          SettingsTile(icon: Icons.rate_review_outlined, title: 'Send feedback', subtitle: 'Tell us what to improve', onTap: () => context.push('$base/help/feedback')),
          SettingsTile(icon: Icons.bug_report_outlined, title: 'Report an issue', subtitle: 'Something is not working', onTap: () => context.push('$base/help/issue')),
        ]),
        SettingsGroup(title: 'History', children: [
          SettingsTile(icon: Icons.history_rounded, title: 'My messages', subtitle: 'What you sent us', onTap: () => context.push('$base/help/messages')),
        ]),
      ],
    );
  }
}

class _FormKind {
  const _FormKind(this.title, this.subjectLabel, this.messageLabel, this.hint, this.done);
  final String title;
  final String subjectLabel;
  final String messageLabel;
  final String hint;
  final String done;
}

const _kinds = {
  'support': _FormKind('Contact support', 'Subject', 'How can we help?', 'Describe what you need help with.', 'We got your message and will reply to your account e-mail.'),
  'feedback': _FormKind('Send feedback', 'Title', 'Your feedback', 'What do you like? What should be better?', 'Thank you! Your feedback helps us improve ZURUV.'),
  'issue': _FormKind('Report an issue', 'What went wrong?', 'Details', 'What did you do, and what happened instead?', 'Thanks for the report. We will look into it.'),
};

/// One form for support, feedback and issue reports: validated, sent to the API, with loading,
/// error and success states.
class SupportFormScreen extends ConsumerStatefulWidget {
  const SupportFormScreen({super.key, required this.kind});
  final String kind;

  @override
  ConsumerState<SupportFormScreen> createState() => _SupportFormScreenState();
}

class _SupportFormScreenState extends ConsumerState<SupportFormScreen> {
  final _form = GlobalKey<FormState>();
  final _subject = TextEditingController();
  final _message = TextEditingController();
  bool _sending = false;
  bool _sent = false;
  String? _error;

  _FormKind get _k => _kinds[widget.kind] ?? _kinds['support']!;

  @override
  void dispose() {
    _subject.dispose();
    _message.dispose();
    super.dispose();
  }

  String get _platform => kIsWeb
      ? 'web'
      : switch (defaultTargetPlatform) {
          TargetPlatform.android => 'android',
          TargetPlatform.iOS => 'ios',
          _ => 'other',
        };

  Future<void> _send() async {
    if (!_form.currentState!.validate()) return;
    setState(() {
      _sending = true;
      _error = null;
    });
    try {
      String? version;
      try {
        final info = await PackageInfo.fromPlatform();
        version = '${info.version}+${info.buildNumber}';
      } catch (_) {}
      await ref.read(settingsRepositoryProvider).sendTicket(
            kind: widget.kind,
            subject: _subject.text.trim(),
            message: _message.text.trim(),
            appVersion: version,
            platform: _platform,
          );
      ref.invalidate(myTicketsProvider);
      if (mounted) setState(() => _sent = true);
    } catch (e) {
      if (mounted) setState(() => _error = errorMessage(e));
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    if (_sent) {
      return Scaffold(
        appBar: AppBar(title: Text(_k.title)),
        body: ResponsivePage(
          maxWidth: 480,
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.check_circle_rounded, size: 72, color: ZuruvColors.success),
              const SizedBox(height: Gap.lg),
              Text(_k.done, textAlign: TextAlign.center, style: theme.textTheme.titleMedium),
              const SizedBox(height: Gap.xxl),
              FilledButton(onPressed: () => context.pop(), child: const Text('Done')),
            ],
          ),
        ),
      );
    }
    return Scaffold(
      appBar: AppBar(title: Text(_k.title)),
      body: SafeArea(
        child: ResponsivePage(
          maxWidth: 560,
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(vertical: 16),
            child: Form(
              key: _form,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (_error != null) AuthBanner(message: _error!),
                  TextFormField(
                    controller: _subject,
                    textCapitalization: TextCapitalization.sentences,
                    maxLength: 120,
                    decoration: InputDecoration(labelText: _k.subjectLabel),
                    validator: (v) => (v ?? '').trim().length < 3 ? 'Enter at least 3 characters' : null,
                  ),
                  const SizedBox(height: Gap.sm),
                  TextFormField(
                    controller: _message,
                    textCapitalization: TextCapitalization.sentences,
                    minLines: 5,
                    maxLines: 10,
                    maxLength: 2000,
                    decoration: InputDecoration(labelText: _k.messageLabel, hintText: _k.hint, alignLabelWithHint: true),
                    validator: (v) => (v ?? '').trim().length < 10 ? 'Please write at least 10 characters' : null,
                  ),
                  const SizedBox(height: Gap.lg),
                  LoadingButton(label: 'Send', onPressed: _send, loading: _sending),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

final myTicketsProvider = FutureProvider.autoDispose<List<SupportTicket>>(
  (ref) => ref.watch(settingsRepositoryProvider).tickets(),
);

class MyMessagesScreen extends ConsumerWidget {
  const MyMessagesScreen({super.key});

  static const _labels = {'support': 'Support', 'feedback': 'Feedback', 'issue': 'Issue'};

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final tickets = ref.watch(myTicketsProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('My messages')),
      body: tickets.when(
        loading: () => const LoadingView(),
        error: (e, _) => ErrorView.fromError(e, onRetry: () => ref.invalidate(myTicketsProvider)),
        data: (list) => list.isEmpty
            ? const Center(child: Padding(padding: EdgeInsets.all(24), child: Text('You haven\'t sent us anything yet.')))
            : ResponsivePage(
                maxWidth: 640,
                child: ListView.separated(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  itemCount: list.length,
                  separatorBuilder: (_, __) => const Divider(),
                  itemBuilder: (_, i) {
                    final t = list[i];
                    final d = t.createdAt;
                    return ListTile(
                      contentPadding: EdgeInsets.zero,
                      title: Text(t.subject),
                      subtitle: Text('${_labels[t.kind] ?? t.kind} · ${d.day.toString().padLeft(2, '0')}/${d.month.toString().padLeft(2, '0')}/${d.year}'),
                      trailing: Chip(label: Text(t.status == 'open' ? 'Received' : 'Closed')),
                    );
                  },
                ),
              ),
      ),
    );
  }
}
