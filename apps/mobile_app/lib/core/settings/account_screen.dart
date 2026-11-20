import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';

import 'package:zuruv/core/constants/tokens.dart';
import 'package:zuruv/core/network/api_helpers.dart';
import 'package:zuruv/core/settings/app_settings.dart';
import 'package:zuruv/core/settings/settings_repository.dart';
import 'package:zuruv/core/settings/settings_widgets.dart';

/// Account information, password change (Supabase Auth) and the account-deletion request.
class AccountScreen extends ConsumerStatefulWidget {
  const AccountScreen({super.key});

  @override
  ConsumerState<AccountScreen> createState() => _AccountScreenState();
}

class _AccountScreenState extends ConsumerState<AccountScreen> {
  final _form = GlobalKey<FormState>();
  final _current = TextEditingController();
  final _new = TextEditingController();
  final _confirm = TextEditingController();
  bool _changing = false;
  bool _deleting = false;
  String? _passwordError;

  @override
  void dispose() {
    _current.dispose();
    _new.dispose();
    _confirm.dispose();
    super.dispose();
  }

  Future<void> _changePassword() async {
    if (!_form.currentState!.validate()) return;
    setState(() {
      _changing = true;
      _passwordError = null;
    });
    try {
      await ref.read(authControllerProvider.notifier).changePassword(currentPassword: _current.text, newPassword: _new.text);
      if (!mounted) return;
      _current.clear();
      _new.clear();
      _confirm.clear();
      showSnack(context, 'Password changed');
    } on AuthActionException catch (e) {
      if (mounted) setState(() => _passwordError = e.message);
    } catch (e) {
      if (mounted) setState(() => _passwordError = errorMessage(e));
    } finally {
      if (mounted) setState(() => _changing = false);
    }
  }

  Future<void> _requestDeletion() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Request account deletion?'),
        content: const Text(
          'Our team will review your request and delete your account and personal data. '
          'Upcoming bookings and unsettled payments may need to be completed first. '
          'You can cancel the request here at any time before then. Nothing is deleted right now.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Keep my account')),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: TextButton.styleFrom(foregroundColor: ZuruvColors.error),
            child: const Text('Send request'),
          ),
        ],
      ),
    );
    if (ok != true) return;
    await _deletion(() => ref.read(settingsRepositoryProvider).requestDeletion(), 'Deletion request sent');
  }

  Future<void> _deletion(Future<UserProfile> Function() call, String done) async {
    setState(() => _deleting = true);
    try {
      final updated = await call();
      ref.read(authControllerProvider.notifier).setProfile(updated);
      if (mounted) showSnack(context, done);
    } catch (e) {
      if (mounted) showSnack(context, errorMessage(e));
    } finally {
      if (mounted) setState(() => _deleting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final auth = ref.watch(authControllerProvider);
    if (auth is! Authenticated) return const Scaffold(body: LoadingView());
    final profile = auth.profile;
    final isOwner = ref.watch(isOwnerProvider);
    final pending = profile.deletionRequestedAt;

    return SettingsPage(
      title: 'Account',
      children: [
        SettingsGroup(title: 'Account information', children: [
          _InfoRow(icon: Icons.person_outline_rounded, label: 'Name', value: profile.fullName),
          _InfoRow(icon: Icons.mail_outline_rounded, label: 'E-mail', value: profile.email ?? 'Not set'),
          _InfoRow(icon: Icons.phone_outlined, label: 'Phone', value: (profile.phone ?? '').isEmpty ? 'Not set' : profile.phone!),
          _InfoRow(icon: Icons.badge_outlined, label: 'Account type', value: isOwner ? 'Venue owner' : 'Player'),
          _InfoRow(icon: Icons.verified_user_outlined, label: 'Status', value: profile.isActive ? 'Active' : 'Suspended'),
        ]),
        SettingsGroup(
          title: 'Change password',
          footer: 'Signed up with Google? Use "Forgot password" on the sign-in screen to set a password first.',
          children: [
            Padding(
              padding: const EdgeInsets.all(16),
              child: Form(
                key: _form,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    if (_passwordError != null) AuthBanner(message: _passwordError!),
                    TextFormField(
                      controller: _current,
                      obscureText: true,
                      autofillHints: const [AutofillHints.password],
                      decoration: const InputDecoration(labelText: 'Current password'),
                      validator: (v) => (v == null || v.isEmpty) ? 'Enter your current password' : null,
                    ),
                    const SizedBox(height: Gap.md),
                    TextFormField(
                      controller: _new,
                      obscureText: true,
                      autofillHints: const [AutofillHints.newPassword],
                      decoration: const InputDecoration(labelText: 'New password'),
                      validator: (v) {
                        final base = Validators.password(v);
                        if (base != null) return base;
                        return v == _current.text ? 'Choose a password you haven\'t used here' : null;
                      },
                    ),
                    const SizedBox(height: Gap.md),
                    TextFormField(
                      controller: _confirm,
                      obscureText: true,
                      decoration: const InputDecoration(labelText: 'Confirm new password'),
                      validator: (v) => v == _new.text ? null : 'Passwords don\'t match',
                    ),
                    const SizedBox(height: Gap.lg),
                    LoadingButton(label: 'Update password', onPressed: _changePassword, loading: _changing),
                  ],
                ),
              ),
            ),
          ],
        ),
        SettingsGroup(
          title: 'Delete account',
          children: [
            Padding(
              padding: const EdgeInsets.all(16),
              child: pending == null
                  ? Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Text(
                          'Ask us to permanently delete your account and personal data. '
                          'We review every request, and you can cancel it until it is processed.',
                          style: theme.textTheme.bodyMedium,
                        ),
                        const SizedBox(height: Gap.lg),
                        OutlinedButton.icon(
                          onPressed: _deleting ? null : _requestDeletion,
                          style: OutlinedButton.styleFrom(foregroundColor: ZuruvColors.error),
                          icon: const Icon(Icons.delete_outline_rounded),
                          label: Text(_deleting ? 'Sending…' : 'Request account deletion'),
                        ),
                      ],
                    )
                  : Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        AuthBanner(
                          message: 'Deletion requested on ${_date(pending)}. Your account stays active until our team processes it.',
                        ),
                        OutlinedButton(
                          onPressed: _deleting ? null : () => _deletion(() => ref.read(settingsRepositoryProvider).cancelDeletion(), 'Request cancelled'),
                          child: Text(_deleting ? 'Please wait…' : 'Cancel deletion request'),
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

String _date(DateTime d) {
  final l = d.toLocal();
  return '${l.day.toString().padLeft(2, '0')}/${l.month.toString().padLeft(2, '0')}/${l.year}';
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({required this.icon, required this.label, required this.value});
  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ListTile(
      leading: Icon(icon, color: theme.colorScheme.primary),
      title: Text(label, style: theme.textTheme.bodySmall),
      subtitle: Text(value, style: theme.textTheme.bodyLarge),
    );
  }
}
