import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../config/app_env.dart';
import '../../widgets/loading_view.dart';
import '../models.dart';
import '../providers.dart';
import '../state.dart';
import 'auth_widgets.dart';

String _message(Object e) => e is AuthActionException ? e.message : 'Something went wrong. Please try again.';

// ------------------------------------------------------------------------------------------------
class SplashScreen extends StatelessWidget {
  const SplashScreen({super.key});

  @override
  Widget build(BuildContext context) => const Scaffold(body: LoadingView(message: 'Loading...'));
}

// ------------------------------------------------------------------------------------------------
class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _form = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _loading = false;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _run(Future<void> Function() action) async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      await action();
    } catch (e) {
      if (mounted) setState(() => _error = _message(e));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _submit() {
    if (!_form.currentState!.validate()) return;
    _run(() => ref.read(authControllerProvider.notifier).signIn(_email.text.trim(), _password.text));
  }

  @override
  Widget build(BuildContext context) {
    final cfg = ref.watch(authUiConfigProvider);
    final state = ref.watch(authControllerProvider);
    final notice = state is Unauthenticated ? state.notice : null;
    final controller = ref.read(authControllerProvider.notifier);

    return AuthScaffold(
      appName: cfg.appName,
      title: 'Welcome back',
      subtitle: cfg.tagline,
      children: [
        if (notice != null) AuthBanner(message: notice, isError: false),
        if (_error != null) AuthBanner(message: _error!),
        Form(
          key: _form,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              TextFormField(
                controller: _email,
                keyboardType: TextInputType.emailAddress,
                autofillHints: const [AutofillHints.email],
                textInputAction: TextInputAction.next,
                validator: Validators.email,
                decoration: const InputDecoration(labelText: 'E-mail'),
              ),
              const SizedBox(height: 16),
              PasswordField(
                controller: _password,
                validator: (v) => Validators.required(v, 'your password'),
                onSubmitted: (_) => _submit(),
              ),
              Align(
                alignment: Alignment.centerRight,
                child: TextButton(
                  onPressed: () => context.push('/forgot-password'),
                  child: const Text('Forgot password?'),
                ),
              ),
              LoadingButton(label: 'Sign in', loading: _loading, onPressed: _submit),
            ],
          ),
        ),
        if (AppEnv.googleAuthEnabled || AppEnv.appleAuthEnabled || AppEnv.phoneAuthEnabled) ...[
          const SizedBox(height: 24),
          const Row(children: [Expanded(child: Divider()), Padding(padding: EdgeInsets.all(8), child: Text('or')), Expanded(child: Divider())]),
          const SizedBox(height: 8),
          if (AppEnv.googleAuthEnabled)
            OutlinedButton.icon(
              onPressed: _loading ? null : () => _run(() => controller.signInWithOAuth(OAuthKind.google)),
              icon: const Icon(Icons.g_mobiledata, size: 28),
              label: const Text('Continue with Google'),
            ),
          if (AppEnv.appleAuthEnabled && defaultTargetPlatform == TargetPlatform.iOS) ...[
            const SizedBox(height: 12),
            OutlinedButton.icon(
              onPressed: _loading ? null : () => _run(() => controller.signInWithOAuth(OAuthKind.apple)),
              icon: const Icon(Icons.apple),
              label: const Text('Continue with Apple'),
            ),
          ],
          if (AppEnv.phoneAuthEnabled) ...[
            const SizedBox(height: 12),
            OutlinedButton.icon(
              onPressed: _loading ? null : () => context.push('/phone'),
              icon: const Icon(Icons.phone_outlined),
              label: const Text('Continue with phone'),
            ),
          ],
        ],
        const SizedBox(height: 24),
        Wrap(
          alignment: WrapAlignment.center,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            const Text("Don't have an account?"),
            TextButton(onPressed: () => context.push('/register'), child: const Text('Create account')),
          ],
        ),
      ],
    );
  }
}

// ------------------------------------------------------------------------------------------------
class RegisterScreen extends ConsumerStatefulWidget {
  const RegisterScreen({super.key});

  @override
  ConsumerState<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends ConsumerState<RegisterScreen> {
  final _form = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _business = TextEditingController();
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _confirm = TextEditingController();
  bool _loading = false;
  String? _error;
  String? _confirmationSentTo;

  @override
  void dispose() {
    for (final c in [_name, _business, _email, _password, _confirm]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _submit() async {
    final isOwner = ref.read(signUpRoleProvider) == AppRole.owner;
    if (!_form.currentState!.validate()) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final outcome = await ref.read(authControllerProvider.notifier).register(
            email: _email.text.trim(),
            password: _password.text,
            fullName: _name.text.trim(),
            role: ref.read(signUpRoleProvider),
            businessName: isOwner ? _business.text.trim() : null,
          );
      if (outcome == SignUpOutcome.confirmationRequired && mounted) {
        setState(() => _confirmationSentTo = _email.text.trim());
      }
      // signedIn: the auth controller takes over and the router moves on.
    } catch (e) {
      if (mounted) setState(() => _error = _message(e));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final cfg = ref.watch(authUiConfigProvider);
    final isOwner = ref.watch(signUpRoleProvider) == AppRole.owner;

    if (_confirmationSentTo != null) {
      return AuthScaffold(
        appName: cfg.appName,
        title: 'Check your e-mail',
        subtitle: 'We sent a verification link to $_confirmationSentTo. Open it, then sign in.',
        showBack: true,
        children: [FilledButton(onPressed: () => context.go('/login'), child: const Text('Back to sign in'))],
      );
    }

    return AuthScaffold(
      appName: cfg.appName,
      title: isOwner ? 'Register your business' : 'Create your account',
      showBack: true,
      children: [
        if (_error != null) AuthBanner(message: _error!),
        const AccountTypePicker(),
        const SizedBox(height: 16),
        Form(
          key: _form,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              TextFormField(
                controller: _name,
                textCapitalization: TextCapitalization.words,
                textInputAction: TextInputAction.next,
                validator: (v) => Validators.required(v, 'your name'),
                decoration: const InputDecoration(labelText: 'Full name'),
              ),
              if (isOwner) ...[
                const SizedBox(height: 16),
                TextFormField(
                  controller: _business,
                  textCapitalization: TextCapitalization.words,
                  textInputAction: TextInputAction.next,
                  validator: (v) => Validators.required(v, 'your business name'),
                  decoration: const InputDecoration(labelText: 'Business name'),
                ),
              ],
              const SizedBox(height: 16),
              TextFormField(
                controller: _email,
                keyboardType: TextInputType.emailAddress,
                autofillHints: const [AutofillHints.email],
                textInputAction: TextInputAction.next,
                validator: Validators.email,
                decoration: const InputDecoration(labelText: 'E-mail'),
              ),
              const SizedBox(height: 16),
              PasswordField(controller: _password, validator: Validators.password),
              const SizedBox(height: 16),
              PasswordField(
                controller: _confirm,
                label: 'Confirm password',
                validator: (v) => v == _password.text ? null : 'Passwords do not match',
                onSubmitted: (_) => _submit(),
              ),
              const SizedBox(height: 24),
              LoadingButton(label: 'Create account', loading: _loading, onPressed: _submit),
            ],
          ),
        ),
      ],
    );
  }
}

// ------------------------------------------------------------------------------------------------
class ForgotPasswordScreen extends ConsumerStatefulWidget {
  const ForgotPasswordScreen({super.key});

  @override
  ConsumerState<ForgotPasswordScreen> createState() => _ForgotPasswordScreenState();
}

class _ForgotPasswordScreenState extends ConsumerState<ForgotPasswordScreen> {
  final _form = GlobalKey<FormState>();
  final _email = TextEditingController();
  bool _loading = false;
  bool _sent = false;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_form.currentState!.validate()) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      await ref.read(authControllerProvider.notifier).sendPasswordReset(_email.text.trim());
      if (mounted) setState(() => _sent = true);
    } catch (e) {
      if (mounted) setState(() => _error = _message(e));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final cfg = ref.watch(authUiConfigProvider);
    return AuthScaffold(
      appName: cfg.appName,
      title: 'Reset your password',
      subtitle: 'Enter your e-mail and we will send you a reset link.',
      showBack: true,
      children: [
        if (_sent)
          const AuthBanner(
            isError: false,
            message: 'If an account exists for that e-mail, a reset link is on its way. Open it on this device.',
          ),
        if (_error != null) AuthBanner(message: _error!),
        Form(
          key: _form,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              TextFormField(
                controller: _email,
                keyboardType: TextInputType.emailAddress,
                validator: Validators.email,
                decoration: const InputDecoration(labelText: 'E-mail'),
                onFieldSubmitted: (_) => _submit(),
              ),
              const SizedBox(height: 24),
              LoadingButton(label: _sent ? 'Send again' : 'Send reset link', loading: _loading, onPressed: _submit),
            ],
          ),
        ),
      ],
    );
  }
}

// ------------------------------------------------------------------------------------------------
class ResetPasswordScreen extends ConsumerStatefulWidget {
  const ResetPasswordScreen({super.key});

  @override
  ConsumerState<ResetPasswordScreen> createState() => _ResetPasswordScreenState();
}

class _ResetPasswordScreenState extends ConsumerState<ResetPasswordScreen> {
  final _form = GlobalKey<FormState>();
  final _password = TextEditingController();
  final _confirm = TextEditingController();
  bool _loading = false;
  String? _error;

  @override
  void dispose() {
    _password.dispose();
    _confirm.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_form.currentState!.validate()) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      await ref.read(authControllerProvider.notifier).setNewPassword(_password.text);
    } catch (e) {
      if (mounted) setState(() => _error = _message(e));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final cfg = ref.watch(authUiConfigProvider);
    return AuthScaffold(
      appName: cfg.appName,
      title: 'Choose a new password',
      children: [
        if (_error != null) AuthBanner(message: _error!),
        Form(
          key: _form,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              PasswordField(controller: _password, label: 'New password', validator: Validators.password),
              const SizedBox(height: 16),
              PasswordField(
                controller: _confirm,
                label: 'Confirm new password',
                validator: (v) => v == _password.text ? null : 'Passwords do not match',
                onSubmitted: (_) => _submit(),
              ),
              const SizedBox(height: 24),
              LoadingButton(label: 'Update password', loading: _loading, onPressed: _submit),
            ],
          ),
        ),
      ],
    );
  }
}

// ------------------------------------------------------------------------------------------------
/// Phone OTP sign-in. Only reachable when PHONE_AUTH_ENABLED is set (needs an SMS provider
/// configured in Supabase: open question N24).
class PhoneSignInScreen extends ConsumerStatefulWidget {
  const PhoneSignInScreen({super.key});

  @override
  ConsumerState<PhoneSignInScreen> createState() => _PhoneSignInScreenState();
}

class _PhoneSignInScreenState extends ConsumerState<PhoneSignInScreen> {
  final _form = GlobalKey<FormState>();
  final _phone = TextEditingController();
  final _code = TextEditingController();
  bool _loading = false;
  bool _codeSent = false;
  String? _error;

  @override
  void dispose() {
    _phone.dispose();
    _code.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_form.currentState!.validate()) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    final controller = ref.read(authControllerProvider.notifier);
    try {
      if (!_codeSent) {
        await controller.sendPhoneOtp(_phone.text.trim());
        if (mounted) setState(() => _codeSent = true);
      } else {
        await controller.verifyPhoneOtp(_phone.text.trim(), _code.text.trim());
      }
    } catch (e) {
      if (mounted) setState(() => _error = _message(e));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final cfg = ref.watch(authUiConfigProvider);
    return AuthScaffold(
      appName: cfg.appName,
      title: 'Continue with phone',
      subtitle: _codeSent ? 'Enter the 6-digit code we sent you.' : 'We will text you a verification code.',
      showBack: true,
      children: [
        if (_error != null) AuthBanner(message: _error!),
        Form(
          key: _form,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              TextFormField(
                controller: _phone,
                enabled: !_codeSent,
                keyboardType: TextInputType.phone,
                validator: Validators.phone,
                decoration: const InputDecoration(labelText: 'Phone number', hintText: '+919876543210'),
              ),
              if (_codeSent) ...[
                const SizedBox(height: 16),
                TextFormField(
                  controller: _code,
                  keyboardType: TextInputType.number,
                  autofillHints: const [AutofillHints.oneTimeCode],
                  validator: (v) => (v == null || v.trim().length < 4) ? 'Enter the code' : null,
                  decoration: const InputDecoration(labelText: 'Verification code'),
                  onFieldSubmitted: (_) => _submit(),
                ),
              ],
              const SizedBox(height: 24),
              LoadingButton(label: _codeSent ? 'Verify' : 'Send code', loading: _loading, onPressed: _submit),
            ],
          ),
        ),
      ],
    );
  }
}

// ------------------------------------------------------------------------------------------------
class CompleteProfileScreen extends ConsumerStatefulWidget {
  const CompleteProfileScreen({super.key});

  @override
  ConsumerState<CompleteProfileScreen> createState() => _CompleteProfileScreenState();
}

class _CompleteProfileScreenState extends ConsumerState<CompleteProfileScreen> {
  final _form = GlobalKey<FormState>();
  late final TextEditingController _name;
  late final TextEditingController _business;
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    final s = ref.read(authControllerProvider);
    _name = TextEditingController(text: s is NeedsProfile ? s.prefillName ?? '' : '');
    _business = TextEditingController(text: s is NeedsProfile ? s.prefillBusinessName ?? '' : '');
  }

  @override
  void dispose() {
    _name.dispose();
    _business.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final role = ref.read(signUpRoleProvider);
    final isOwner = role == AppRole.owner;
    if (!_form.currentState!.validate()) return;
    setState(() => _loading = true);
    await ref.read(authControllerProvider.notifier).completeProfile(
          role: role,
          fullName: _name.text.trim(),
          businessName: isOwner ? _business.text.trim() : null,
        );
    if (mounted) setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    final cfg = ref.watch(authUiConfigProvider);
    final s = ref.watch(authControllerProvider);
    final isOwner = ref.watch(signUpRoleProvider) == AppRole.owner;
    final error = s is NeedsProfile ? s.error : null;
    return AuthScaffold(
      appName: cfg.appName,
      title: 'Complete your profile',
      subtitle: 'Choose your account type and add a few details to finish setting up.',
      children: [
        if (error != null) AuthBanner(message: error),
        const AccountTypePicker(),
        const SizedBox(height: 16),
        Form(
          key: _form,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              TextFormField(
                controller: _name,
                textCapitalization: TextCapitalization.words,
                validator: (v) => Validators.required(v, 'your name'),
                decoration: const InputDecoration(labelText: 'Full name'),
              ),
              if (isOwner) ...[
                const SizedBox(height: 16),
                TextFormField(
                  controller: _business,
                  textCapitalization: TextCapitalization.words,
                  validator: (v) => Validators.required(v, 'your business name'),
                  decoration: const InputDecoration(labelText: 'Business name'),
                ),
              ],
              const SizedBox(height: 24),
              LoadingButton(label: 'Continue', loading: _loading, onPressed: _submit),
              TextButton(
                onPressed: () => ref.read(authControllerProvider.notifier).signOut(),
                child: const Text('Sign out'),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

// ------------------------------------------------------------------------------------------------
class SuspendedScreen extends ConsumerWidget {
  const SuspendedScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final cfg = ref.watch(authUiConfigProvider);
    return AuthScaffold(
      appName: cfg.appName,
      title: 'Account suspended',
      subtitle: 'This account cannot be used right now. Please contact support.',
      children: [
        OutlinedButton(
          onPressed: () => ref.read(authControllerProvider.notifier).signOut(),
          child: const Text('Sign out'),
        ),
      ],
    );
  }
}

class AuthErrorScreen extends ConsumerWidget {
  const AuthErrorScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final cfg = ref.watch(authUiConfigProvider);
    final s = ref.watch(authControllerProvider);
    final controller = ref.read(authControllerProvider.notifier);
    return AuthScaffold(
      appName: cfg.appName,
      title: "Can't reach ZURUV",
      subtitle: s is AuthFailure ? s.message : null,
      children: [
        FilledButton(onPressed: controller.resolve, child: const Text('Try again')),
        const SizedBox(height: 12),
        OutlinedButton(onPressed: controller.signOut, child: const Text('Sign out')),
      ],
    );
  }
}
