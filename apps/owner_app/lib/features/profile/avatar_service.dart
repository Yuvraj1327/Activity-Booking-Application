import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../../core/config/app_config.dart';

class AvatarException implements Exception {
  const AvatarException(this.message);
  final String message;
}

/// Profile pictures live in the PRIVATE `profile-images` bucket, in the user's own folder
/// (`<user id>/<name>.jpg|jpeg|png|webp`). Storage policies enforce that folder; the API checks
/// it again when the path is saved. Reading uses short-lived signed URLs.
abstract class AvatarService {
  /// Uploads and returns the storage path to save with `PATCH /profiles/me`.
  Future<String> upload({required String userId, required Uint8List bytes, required String extension});

  Future<String?> signedUrl(String path);

  /// Best effort: removes a previous picture after a new one is saved.
  Future<void> delete(String path);
}

class SupabaseAvatarService implements AvatarService {
  const SupabaseAvatarService();

  static const _bucket = 'profile-images';

  StorageFileApi get _storage => Supabase.instance.client.storage.from(_bucket);

  @override
  Future<String> upload({required String userId, required Uint8List bytes, required String extension}) async {
    final ext = extension.toLowerCase().replaceAll('.', '');
    if (!AppConfig.avatarExtensions.contains(ext)) {
      throw const AvatarException('Choose a JPG, PNG or WebP image.');
    }
    if (bytes.lengthInBytes > AppConfig.avatarMaxBytes) {
      throw const AvatarException('That image is larger than 2 MB. Choose a smaller one.');
    }
    if (!AppEnv.supabaseConfigured) {
      throw const AvatarException('Photo upload is not configured in this build.');
    }
    final path = '$userId/avatar-${DateTime.now().millisecondsSinceEpoch}.$ext';
    try {
      await _storage.uploadBinary(
        path,
        bytes,
        fileOptions: FileOptions(contentType: ext == 'jpg' ? 'image/jpeg' : 'image/$ext', upsert: false),
      );
    } on StorageException catch (e) {
      throw AvatarException(e.statusCode == '403' ? 'You are not allowed to upload this image.' : 'Could not upload the image.');
    }
    return path;
  }

  @override
  Future<String?> signedUrl(String path) async {
    if (!AppEnv.supabaseConfigured) return null;
    try {
      return await _storage.createSignedUrl(path, 3600);
    } catch (_) {
      return null;
    }
  }

  @override
  Future<void> delete(String path) async {
    try {
      await _storage.remove([path]);
    } catch (_) {
      // Orphaned files are harmless; they stay inside the user's private folder.
    }
  }
}

final avatarServiceProvider = Provider<AvatarService>((ref) => const SupabaseAvatarService());

/// Signed URL for the stored avatar path (null when there is no avatar or it can't be signed).
final avatarUrlProvider = FutureProvider.autoDispose.family<String?, String?>((ref, path) async {
  if (path == null || path.isEmpty) return null;
  return ref.watch(avatarServiceProvider).signedUrl(path);
});
