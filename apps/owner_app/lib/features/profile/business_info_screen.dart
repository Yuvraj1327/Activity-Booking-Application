import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:go_router/go_router.dart';

import '../../core/constants/tokens.dart';
import '../../core/network/api_helpers.dart';
import '../../shared/models/models.dart';
import '../../shared/repositories/owner_repository.dart';
import 'profile_screen.dart';

/// Business name, phone, e-mail and address (`GET/PATCH /owners/me`). Only the signed-in owner's
/// own record can be read or changed.
class BusinessInfoScreen extends ConsumerStatefulWidget {
  const BusinessInfoScreen({super.key});

  @override
  ConsumerState<BusinessInfoScreen> createState() => _BusinessInfoScreenState();
}

class _BusinessInfoScreenState extends ConsumerState<BusinessInfoScreen> {
  final _form = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _phone = TextEditingController();
  final _email = TextEditingController();
  final _address = TextEditingController();
  OwnerBusiness? _original;
  bool _loading = true;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    for (final c in [_name, _phone, _email, _address]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final b = await ref.read(ownerRepositoryProvider).business();
      if (!mounted) return;
      _original = b;
      _name.text = b.businessName;
      _phone.text = b.businessPhone ?? '';
      _email.text = b.businessEmail ?? '';
      _address.text = b.businessAddress ?? '';
      setState(() => _loading = false);
    } catch (e) {
      if (mounted) {
        setState(() {
          _loading = false;
          _error = errorMessage(e);
        });
      }
    }
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    final o = _original!;
    final changes = <String, dynamic>{};
    void diff(String key, String text, String? before) {
      final t = text.trim();
      if (t != (before ?? '')) changes[key] = t.isEmpty ? null : t;
    }

    diff('business_name', _name.text, o.businessName);
    diff('business_phone', _phone.text, o.businessPhone);
    diff('business_email', _email.text, o.businessEmail);
    diff('business_address', _address.text, o.businessAddress);
    if (changes.isEmpty) {
      context.pop();
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await ref.read(ownerRepositoryProvider).updateBusiness(changes);
      ref.invalidate(businessProvider);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Business information saved')));
      context.pop();
    } catch (e) {
      if (mounted) setState(() => _error = errorMessage(e));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Business information')),
      body: _loading
          ? const LoadingView()
          : _original == null
              ? ErrorView(message: _error ?? 'Could not load your business.', onRetry: _load)
              : SafeArea(
                  child: ResponsivePage(
                    maxWidth: 480,
                    child: SingleChildScrollView(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      child: Form(
                        key: _form,
                        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                          if (_error != null) ...[AuthBanner(message: _error!), const SizedBox(height: Gap.lg)],
                          TextFormField(
                            controller: _name,
                            textCapitalization: TextCapitalization.words,
                            decoration: const InputDecoration(labelText: 'Business name'),
                            validator: (v) => Validators.required(v, 'your business name'),
                          ),
                          const SizedBox(height: Gap.lg),
                          TextFormField(
                            controller: _phone,
                            keyboardType: TextInputType.phone,
                            decoration: const InputDecoration(labelText: 'Business phone (optional)', hintText: '+919876543210'),
                            validator: (v) => (v == null || v.trim().isEmpty) ? null : Validators.phone(v),
                          ),
                          const SizedBox(height: Gap.lg),
                          TextFormField(
                            controller: _email,
                            keyboardType: TextInputType.emailAddress,
                            decoration: const InputDecoration(labelText: 'Business e-mail (optional)'),
                            validator: (v) => (v == null || v.trim().isEmpty) ? null : Validators.email(v),
                          ),
                          const SizedBox(height: Gap.lg),
                          TextFormField(
                            controller: _address,
                            minLines: 2,
                            maxLines: 4,
                            decoration: const InputDecoration(labelText: 'Business address (optional)', alignLabelWithHint: true),
                          ),
                          const SizedBox(height: 28),
                          LoadingButton(label: 'Save changes', onPressed: _save, loading: _saving),
                        ]),
                      ),
                    ),
                  ),
                ),
    );
  }
}
