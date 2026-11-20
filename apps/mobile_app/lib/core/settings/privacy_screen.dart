import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:geolocator/geolocator.dart';
import 'package:go_router/go_router.dart';

import 'package:zuruv/core/network/api_helpers.dart';
import 'package:zuruv/core/settings/app_settings.dart';
import 'package:zuruv/core/settings/settings_widgets.dart';

/// Permissions the app uses, this device's session, and sign-out (this device or all devices).
class PrivacyScreen extends ConsumerStatefulWidget {
  const PrivacyScreen({super.key});

  @override
  ConsumerState<PrivacyScreen> createState() => _PrivacyScreenState();
}

class _PrivacyScreenState extends ConsumerState<PrivacyScreen> with WidgetsBindingObserver {
  LocationPermission? _location;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _loadPermission();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  /// Coming back from the phone's settings app: re-read the permission.
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) _loadPermission();
  }

  Future<void> _loadPermission() async {
    try {
      final p = await Geolocator.checkPermission();
      if (mounted) setState(() => _location = p);
    } catch (_) {
      if (mounted) setState(() => _location = LocationPermission.unableToDetermine);
    }
  }

  String get _locationLabel => switch (_location) {
        null => 'Checking…',
        LocationPermission.always || LocationPermission.whileInUse => 'Allowed',
        LocationPermission.denied => 'Not allowed yet',
        LocationPermission.deniedForever => 'Blocked in settings',
        LocationPermission.unableToDetermine => 'Unknown',
      };

  Future<void> _openAppSettings() async {
    try {
      final opened = await Geolocator.openAppSettings();
      if (!opened && mounted) showSnack(context, 'Open your phone\'s Settings > Apps > ZURUV to change permissions.');
    } catch (_) {
      if (mounted) showSnack(context, 'Open your phone\'s Settings > Apps > ZURUV to change permissions.');
    }
  }

  Future<void> _signOut({required bool everywhere}) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(everywhere ? 'Sign out of all devices?' : 'Sign out?'),
        content: Text(everywhere
            ? 'You will be signed out here and on every other phone or browser where you use ZURUV. Use this if a device was lost or someone else may have your password.'
            : 'You will need to sign in again on this phone.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Sign out')),
        ],
      ),
    );
    if (ok != true) return;
    setState(() => _busy = true);
    try {
      final auth = ref.read(authControllerProvider.notifier);
      if (everywhere) {
        await auth.signOutEverywhere();
      } else {
        await auth.signOut();
      }
    } catch (e) {
      if (mounted) {
        setState(() => _busy = false);
        showSnack(context, errorMessage(e));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final started = ref.read(authControllerProvider.notifier).sessionStartedAt;
    final base = ref.watch(settingsBaseProvider);
    final device = switch (defaultTargetPlatform) {
      TargetPlatform.android => 'Android phone',
      TargetPlatform.iOS => 'iPhone',
      _ => kIsWeb ? 'Web browser' : 'This device',
    };
    final deniedForever = _location == LocationPermission.deniedForever;
    return SettingsPage(
      title: 'Privacy & security',
      children: [
        SettingsGroup(
          title: 'Permissions',
          footer: 'ZURUV only uses your location to show venues near you. Photos are accessed only when you pick a picture.',
          children: [
            SettingsTile(
              icon: Icons.my_location_rounded,
              title: 'Location',
              subtitle: _locationLabel,
              trailing: TextButton(
                onPressed: _openAppSettings,
                child: Text(deniedForever || _location == LocationPermission.denied ? 'Open settings' : 'Manage'),
              ),
            ),
          ],
        ),
        SettingsGroup(
          title: 'Active sessions',
          footer: 'The list shows this device. To end sessions on other devices, sign out of all devices.',
          children: [
            SettingsTile(
              icon: Icons.smartphone_rounded,
              title: '$device (this device)',
              subtitle: started == null ? 'Signed in now' : 'Signed in ${_when(started)}',
              trailing: const Chip(label: Text('Current')),
            ),
            SettingsTile(
              icon: Icons.devices_other_rounded,
              title: 'Sign out of all devices',
              subtitle: 'Ends every session of your account',
              destructive: true,
              onTap: _busy ? null : () => _signOut(everywhere: true),
            ),
          ],
        ),
        SettingsGroup(title: 'Sign out', children: [
          SettingsTile(
            icon: Icons.logout_rounded,
            title: 'Sign out of this device',
            destructive: true,
            onTap: _busy ? null : () => _signOut(everywhere: false),
          ),
        ]),
        SettingsGroup(title: 'Your data', children: [
          SettingsTile(
            icon: Icons.privacy_tip_outlined,
            title: 'Privacy policy',
            onTap: () => context.push('$base/about/privacy'),
          ),
        ]),
      ],
    );
  }
}

String _when(DateTime t) {
  final d = DateTime.now().difference(t);
  if (d.inMinutes < 1) return 'just now';
  if (d.inHours < 1) return '${d.inMinutes} min ago';
  if (d.inDays < 1) return '${d.inHours} h ago';
  return '${d.inDays} day${d.inDays == 1 ? '' : 's'} ago';
}
