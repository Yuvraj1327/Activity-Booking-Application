import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:package_info_plus/package_info_plus.dart';

import 'package:zuruv/core/constants/tokens.dart';
import 'package:zuruv/core/settings/app_settings.dart';
import 'package:zuruv/core/settings/settings_repository.dart';
import 'package:zuruv/core/settings/settings_widgets.dart';

final packageInfoProvider = FutureProvider<PackageInfo>((ref) => PackageInfo.fromPlatform());

class AboutScreen extends ConsumerWidget {
  const AboutScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final base = ref.watch(settingsBaseProvider);
    final info = ref.watch(packageInfoProvider);
    final theme = Theme.of(context);
    return SettingsPage(
      title: 'About',
      children: [
        const SizedBox(height: Gap.lg),
        Center(child: Image.asset('assets/images/logo.png', height: 72, semanticLabel: 'ZURUV')),
        const SizedBox(height: Gap.sm),
        Center(
          child: Text(
            info.when(
              data: (i) => 'Version ${i.version} (${i.buildNumber})',
              loading: () => 'Version …',
              error: (_, __) => 'Version unavailable',
            ),
            style: theme.textTheme.bodyMedium,
          ),
        ),
        SettingsGroup(children: [
          SettingsTile(icon: Icons.description_outlined, title: 'Terms & Conditions', onTap: () => context.push('$base/about/terms')),
          SettingsTile(icon: Icons.privacy_tip_outlined, title: 'Privacy Policy', onTap: () => context.push('$base/about/privacy')),
        ]),
      ],
    );
  }
}

/// A page published in the admin console, or null when there is none (or it cannot be loaded right now).
final cmsPageProvider = FutureProvider.autoDispose.family<Map<String, dynamic>?, String>((ref, slug) async {
  try {
    return await ref.watch(settingsRepositoryProvider).contentPage(slug);
  } catch (_) {
    return null;
  }
});

/// Shows the legal text published in the admin console (slugs `terms-customer`, `terms-owner`, `privacy`).
/// Until it is published, the final legal text has not been supplied yet (open question in docs/OPEN_QUESTIONS.md), so
/// these pages say so honestly instead of showing invented terms.
class LegalScreen extends ConsumerWidget {
  const LegalScreen({super.key, required this.privacy});
  final bool privacy;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isOwner = ref.watch(isOwnerProvider);
    final slug = privacy ? 'privacy' : (isOwner ? 'terms-owner' : 'terms-customer');
    final managed = ref.watch(cmsPageProvider(slug)).valueOrNull;
    final title = managed != null ? managed['title'] as String : (privacy ? 'Privacy Policy' : 'Terms & Conditions');
    final body = managed != null
        ? managed['body'] as String
        : privacy
        ? 'The ZURUV privacy policy is pending legal review and will be published here before launch.'
        : 'The ZURUV terms and conditions for ${isOwner ? 'venue owners' : 'players'} are pending legal review and will be published here before launch.';
    return SettingsPage(
      title: title,
      children: [
        const SizedBox(height: Gap.lg),
        Text(title, style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: Gap.sm),
        Text(body, style: Theme.of(context).textTheme.bodyMedium),
      ],
    );
  }
}
