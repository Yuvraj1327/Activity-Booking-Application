import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';

import 'package:zuruv/owner/features/profile/avatar_service.dart';

/// Round profile picture: the signed image if there is one, otherwise the user's initial.
class AvatarView extends ConsumerWidget {
  const AvatarView({super.key, required this.name, required this.path, this.radius = 40, this.localBytes});

  final String name;
  final String? path;
  final double radius;

  /// A just-picked image, shown before it has been saved.
  final MemoryImage? localBytes;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final url = ref.watch(avatarUrlProvider(path)).valueOrNull;
    final initial = name.trim().isEmpty ? '?' : name.trim()[0].toUpperCase();
    final fallback = Text(initial, style: TextStyle(fontSize: radius * 0.8, fontWeight: FontWeight.w700, color: Theme.of(context).colorScheme.primary));

    ImageProvider? image;
    if (localBytes != null) {
      image = localBytes;
    } else if (url != null) {
      // Cache by storage path: the signed URL changes on every request.
      image = CachedNetworkImageProvider(url, cacheKey: path);
    }
    return CircleAvatar(
      radius: radius,
      backgroundColor: ZuruvColors.primaryTint,
      backgroundImage: image,
      child: image == null ? fallback : null,
    );
  }
}
