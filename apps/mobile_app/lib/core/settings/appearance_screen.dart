import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:zuruv/core/settings/app_settings.dart';
import 'package:zuruv/core/settings/settings_widgets.dart';

class AppearanceScreen extends ConsumerWidget {
  const AppearanceScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final mode = ref.watch(themeModeProvider);
    const options = [
      (ThemeMode.system, Icons.brightness_auto_rounded, 'System', 'Follow your phone\'s setting'),
      (ThemeMode.light, Icons.light_mode_outlined, 'Light', 'Always use the light theme'),
      (ThemeMode.dark, Icons.dark_mode_outlined, 'Dark', 'Always use the dark theme'),
    ];
    return SettingsPage(
      title: 'Appearance',
      children: [
        SettingsGroup(
          footer: 'Your choice is saved on this phone and used every time you open the app.',
          children: [
            RadioGroup<ThemeMode>(
              groupValue: mode,
              onChanged: (m) {
                if (m != null) ref.read(themeModeProvider.notifier).set(m);
              },
              child: Column(
                children: [
                  for (final (value, icon, title, subtitle) in options)
                    RadioListTile<ThemeMode>(
                      value: value,
                      secondary: Icon(icon, color: Theme.of(context).colorScheme.primary),
                      title: Text(title),
                      subtitle: Text(subtitle),
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
