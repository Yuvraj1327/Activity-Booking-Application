import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';

import '../../core/constants/tokens.dart';
import '../../core/network/api_helpers.dart';
import '../../shared/repositories/profile_repository.dart';
import 'avatar_service.dart';
import 'avatar_view.dart';

/// Edit name, phone and profile picture. E-mail is shown but not editable here.
class EditProfileScreen extends ConsumerStatefulWidget {
  const EditProfileScreen({super.key});

  @override
  ConsumerState<EditProfileScreen> createState() => _EditProfileScreenState();
}

class _EditProfileScreenState extends ConsumerState<EditProfileScreen> {
  final _form = GlobalKey<FormState>();
  late final TextEditingController _name;
  late final TextEditingController _phone;
  late final UserProfile _original;

  Uint8List? _pickedBytes;
  String? _pickedExt;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    final auth = ref.read(authControllerProvider);
    _original = (auth as Authenticated).profile;
    _name = TextEditingController(text: _original.fullName);
    _phone = TextEditingController(text: _original.phone ?? '');
  }

  @override
  void dispose() {
    _name.dispose();
    _phone.dispose();
    super.dispose();
  }

  Future<void> _pickImage() async {
    try {
      final file = await ImagePicker().pickImage(source: ImageSource.gallery, maxWidth: 1024, maxHeight: 1024, imageQuality: 85);
      if (file == null) return;
      final bytes = await file.readAsBytes();
      final dot = file.name.lastIndexOf('.');
      final ext = dot < 0 ? 'jpg' : file.name.substring(dot + 1).toLowerCase();
      setState(() {
        _pickedBytes = bytes;
        _pickedExt = ext;
        _error = null;
      });
    } catch (_) {
      setState(() => _error = 'Could not open your photos. Check the app has permission.');
    }
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    final name = _name.text.trim();
    final phone = _phone.text.trim();
    final changes = <String, dynamic>{
      if (name != _original.fullName) 'full_name': name,
      if (phone != (_original.phone ?? '')) 'phone': phone.isEmpty ? null : phone,
    };
    if (changes.isEmpty && _pickedBytes == null) {
      context.pop();
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final avatars = ref.read(avatarServiceProvider);
      String? uploaded;
      if (_pickedBytes != null) {
        uploaded = await avatars.upload(userId: _original.id, bytes: _pickedBytes!, extension: _pickedExt ?? 'jpg');
        changes['avatar_path'] = uploaded;
      }
      final updated = await ref.read(profileRepositoryProvider).updateProfile(changes);
      ref.read(authControllerProvider.notifier).setProfile(updated);
      if (uploaded != null && _original.avatarPath != null) await avatars.delete(_original.avatarPath!);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Profile updated')));
      context.pop();
    } on AvatarException catch (e) {
      setState(() => _error = e.message);
    } catch (e) {
      setState(() => _error = errorMessage(e));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        leading: IconButton(onPressed: _saving ? null : () => context.pop(), icon: const Icon(Icons.close_rounded)),
        title: Text('Edit profile', style: theme.textTheme.titleLarge),
      ),
      body: SafeArea(
        child: ResponsivePage(
          maxWidth: 480,
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(vertical: 16),
            child: Form(
              key: _form,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Center(
                    child: Stack(
                      children: [
                        AvatarView(
                          name: _name.text,
                          path: _original.avatarPath,
                          radius: 52,
                          localBytes: _pickedBytes == null ? null : MemoryImage(_pickedBytes!),
                        ),
                        Positioned(
                          right: 0,
                          bottom: 0,
                          child: Material(
                            color: theme.colorScheme.primary,
                            shape: const CircleBorder(),
                            child: IconButton(
                              tooltip: 'Change photo',
                              onPressed: _saving ? null : _pickImage,
                              icon: const Icon(Icons.camera_alt_rounded, size: 18, color: Colors.white),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 24),
                  if (_error != null) ...[AuthBanner(message: _error!), const SizedBox(height: 16)],
                  TextFormField(
                    controller: _name,
                    textCapitalization: TextCapitalization.words,
                    decoration: const InputDecoration(labelText: 'Full name'),
                    validator: (v) => Validators.required(v, 'your name'),
                    onChanged: (_) => setState(() {}),
                  ),
                  const SizedBox(height: Gap.lg),
                  TextFormField(
                    controller: _phone,
                    keyboardType: TextInputType.phone,
                    decoration: const InputDecoration(labelText: 'Phone (optional)', hintText: '+919876543210'),
                    validator: (v) => (v == null || v.trim().isEmpty) ? null : Validators.phone(v),
                  ),
                  const SizedBox(height: Gap.lg),
                  TextFormField(
                    initialValue: _original.email ?? '',
                    enabled: false,
                    decoration: const InputDecoration(labelText: 'E-mail', helperText: 'E-mail can\'t be changed here'),
                  ),
                  const SizedBox(height: 28),
                  LoadingButton(label: 'Save changes', onPressed: _save, loading: _saving),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
