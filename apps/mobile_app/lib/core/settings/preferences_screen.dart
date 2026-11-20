import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';

import 'package:zuruv/core/network/api_helpers.dart';
import 'package:zuruv/core/settings/app_settings.dart';
import 'package:zuruv/core/settings/settings_repository.dart';
import 'package:zuruv/core/settings/settings_widgets.dart';
import 'package:zuruv/customer/features/categories/categories_provider.dart';
import 'package:zuruv/customer/features/location/location_controller.dart';
import 'package:zuruv/customer/features/location/location_sheet.dart';

final interestsProvider = FutureProvider.autoDispose<List<String>>(
  (ref) => ref.watch(settingsRepositoryProvider).interests(),
);

/// Language for everyone; sports interests and default city for customers.
class PreferencesScreen extends ConsumerStatefulWidget {
  const PreferencesScreen({super.key});

  @override
  ConsumerState<PreferencesScreen> createState() => _PreferencesScreenState();
}

class _PreferencesScreenState extends ConsumerState<PreferencesScreen> {
  bool _savingLanguage = false;
  bool _savingInterests = false;

  Future<void> _setLanguage(String code) async {
    setState(() => _savingLanguage = true);
    try {
      final updated = await ref.read(settingsRepositoryProvider).setLanguage(code);
      await rememberLanguage(ref, code);
      ref.read(authControllerProvider.notifier).setProfile(updated);
      if (mounted) showSnack(context, 'Language saved');
    } catch (e) {
      if (mounted) showSnack(context, errorMessage(e));
    } finally {
      if (mounted) setState(() => _savingLanguage = false);
    }
  }

  Future<void> _toggleInterest(List<String> current, String id, bool on) async {
    final next = on ? [...current, id] : current.where((e) => e != id).toList();
    setState(() => _savingInterests = true);
    try {
      await ref.read(settingsRepositoryProvider).setInterests(next);
      ref.invalidate(interestsProvider);
      await ref.read(interestsProvider.future);
    } catch (e) {
      if (mounted) showSnack(context, errorMessage(e));
    } finally {
      if (mounted) setState(() => _savingInterests = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isOwner = ref.watch(isOwnerProvider);
    final language = ref.watch(languageCodeProvider);

    return SettingsPage(
      title: 'Preferences',
      children: [
        if (!isOwner) ...[
          SettingsGroup(
            title: 'Sports & interests',
            footer: 'Pick the sports you play. We use them to get you started in the right places.',
            children: [
              Padding(
                padding: const EdgeInsets.all(16),
                child: _InterestChips(saving: _savingInterests, onToggle: _toggleInterest),
              ),
            ],
          ),
          SettingsGroup(title: 'Default city', children: [
            Consumer(builder: (context, ref, _) {
              final city = ref.watch(locationControllerProvider.select((s) => s.city));
              return SettingsTile(
                icon: Icons.place_outlined,
                title: 'City',
                value: city?.name ?? 'Not selected',
                onTap: () => showCitySheet(context),
              );
            }),
          ]),
        ],
        SettingsGroup(
          title: 'Language',
          footer: 'Saved to your account. Dates, numbers and system dialogs follow it now; the rest of the app is still English only.',
          children: [
            if (_savingLanguage) const LinearProgressIndicator(),
            RadioGroup<String>(
              groupValue: language,
              onChanged: (c) {
                if (c != null && c != language && !_savingLanguage) _setLanguage(c);
              },
              child: Column(
                children: [
                  for (final e in supportedLanguages.entries)
                    RadioListTile<String>(
                      value: e.key,
                      title: Text(e.value),
                      secondary: Icon(Icons.translate_rounded, color: theme.colorScheme.primary),
                    ),
                ],
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class _InterestChips extends ConsumerWidget {
  const _InterestChips({required this.saving, required this.onToggle});

  final bool saving;
  final Future<void> Function(List<String> current, String id, bool on) onToggle;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final categories = ref.watch(categoriesProvider);
    final selected = ref.watch(interestsProvider);
    if (categories.isLoading || selected.isLoading) {
      return const Center(child: Padding(padding: EdgeInsets.all(8), child: CircularProgressIndicator()));
    }
    final error = categories.error ?? selected.error;
    if (error != null) {
      return Row(children: [
        Expanded(child: Text(errorMessage(error), style: Theme.of(context).textTheme.bodySmall)),
        TextButton(
          onPressed: () {
            ref.invalidate(categoriesProvider);
            ref.invalidate(interestsProvider);
          },
          child: const Text('Retry'),
        ),
      ]);
    }
    final ids = selected.requireValue;
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        for (final c in categories.requireValue)
          FilterChip(
            label: Text(c.name),
            selected: ids.contains(c.id),
            onSelected: saving ? null : (on) => onToggle(ids, c.id, on),
          ),
      ],
    );
  }
}
