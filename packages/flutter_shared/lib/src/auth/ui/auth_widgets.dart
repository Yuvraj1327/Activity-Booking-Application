import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../theme/zuruv_colors.dart';
import '../../widgets/responsive.dart';
import '../models.dart';
import '../providers.dart';

/// Page frame shared by all auth screens.
class AuthScaffold extends StatelessWidget {
  const AuthScaffold({
    super.key,
    required this.appName,
    required this.title,
    this.subtitle,
    required this.children,
    this.showBack = false,
  });

  final String appName;
  final String title;
  final String? subtitle;
  final List<Widget> children;
  final bool showBack;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: showBack ? AppBar() : null,
      body: SafeArea(
        child: ResponsivePage(
          maxWidth: 480,
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(vertical: 24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (!showBack) ...[
                  Text(appName, style: theme.textTheme.headlineMedium?.copyWith(color: theme.colorScheme.primary)),
                  const SizedBox(height: 24),
                ],
                Text(title, style: theme.textTheme.headlineMedium),
                if (subtitle != null) ...[
                  const SizedBox(height: 8),
                  Text(subtitle!, style: theme.textTheme.bodySmall),
                ],
                const SizedBox(height: 24),
                ...children,
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class AuthBanner extends StatelessWidget {
  const AuthBanner({super.key, required this.message, this.isError = true});

  final String message;
  final bool isError;

  @override
  Widget build(BuildContext context) {
    final color = isError ? ZuruvColors.error : ZuruvColors.success;
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Text(message, style: Theme.of(context).textTheme.bodyMedium, semanticsLabel: message),
    );
  }
}

class LoadingButton extends StatelessWidget {
  const LoadingButton({super.key, required this.label, required this.onPressed, required this.loading});

  final String label;
  final VoidCallback? onPressed;
  final bool loading;

  @override
  Widget build(BuildContext context) {
    return FilledButton(
      onPressed: loading ? null : onPressed,
      child: loading
          ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
          : Text(label),
    );
  }
}

class PasswordField extends StatefulWidget {
  const PasswordField({super.key, required this.controller, this.label = 'Password', this.validator, this.onSubmitted});

  final TextEditingController controller;
  final String label;
  final String? Function(String?)? validator;
  final ValueChanged<String>? onSubmitted;

  @override
  State<PasswordField> createState() => _PasswordFieldState();
}

class _PasswordFieldState extends State<PasswordField> {
  bool _hidden = true;

  @override
  Widget build(BuildContext context) {
    return TextFormField(
      controller: widget.controller,
      obscureText: _hidden,
      autocorrect: false,
      enableSuggestions: false,
      autofillHints: const [AutofillHints.password],
      textInputAction: widget.onSubmitted == null ? TextInputAction.next : TextInputAction.done,
      onFieldSubmitted: widget.onSubmitted,
      validator: widget.validator,
      decoration: InputDecoration(
        labelText: widget.label,
        suffixIcon: IconButton(
          tooltip: _hidden ? 'Show password' : 'Hide password',
          icon: Icon(_hidden ? Icons.visibility_outlined : Icons.visibility_off_outlined),
          onPressed: () => setState(() => _hidden = !_hidden),
        ),
      ),
    );
  }
}

class Validators {
  const Validators._();

  static final _email = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');
  static final _phone = RegExp(r'^\+[1-9][0-9]{6,14}$');

  static String? required(String? v, String what) => (v == null || v.trim().isEmpty) ? 'Enter $what' : null;

  static String? email(String? v) {
    if (v == null || v.trim().isEmpty) return 'Enter your e-mail';
    return _email.hasMatch(v.trim()) ? null : 'Enter a valid e-mail';
  }

  /// Mirrors the minimum configured in Supabase (Auth > Password: 8 characters).
  static String? password(String? v) {
    if (v == null || v.isEmpty) return 'Enter a password';
    return v.length < 8 ? 'Use at least 8 characters' : null;
  }

  static String? phone(String? v) {
    if (v == null || v.trim().isEmpty) return 'Enter your phone number';
    return _phone.hasMatch(v.trim()) ? null : 'Use international format, e.g. +919876543210';
  }
}


/// "I am a ..." choice shown when creating an account. It only decides which profile is requested
/// the first time; the role is then read from the API on every sign-in.
class AccountTypePicker extends ConsumerWidget {
  const AccountTypePicker({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final selected = ref.watch(signUpRoleProvider);
    return SegmentedButton<AppRole>(
      showSelectedIcon: false,
      segments: const [
        ButtonSegment(value: AppRole.customer, icon: Icon(Icons.sports_tennis_rounded), label: Text('Player')),
        ButtonSegment(value: AppRole.owner, icon: Icon(Icons.storefront_rounded), label: Text('Venue owner')),
      ],
      selected: {selected},
      onSelectionChanged: (s) => ref.read(signUpRoleProvider.notifier).state = s.first,
    );
  }
}
