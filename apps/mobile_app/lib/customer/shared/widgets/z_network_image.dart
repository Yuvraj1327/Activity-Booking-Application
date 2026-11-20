import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

/// Venue photo with a cached download, a calm placeholder while loading and a neutral fallback
/// when there is no URL or it fails. Never shows an unrelated stock image.
class ZNetworkImage extends StatelessWidget {
  const ZNetworkImage({
    super.key,
    required this.url,
    this.aspectRatio,
    this.borderRadius = 16,
    this.fit = BoxFit.cover,
    this.semanticLabel,
  });

  final String? url;
  final double? aspectRatio;
  final double borderRadius;
  final BoxFit fit;
  final String? semanticLabel;

  @override
  Widget build(BuildContext context) {
    Widget image = ClipRRect(
      borderRadius: BorderRadius.circular(borderRadius),
      child: url == null
          ? const ImageFallback()
          : CachedNetworkImage(
              imageUrl: url!,
              fit: fit,
              width: double.infinity,
              height: double.infinity,
              fadeInDuration: const Duration(milliseconds: 180),
              placeholder: (_, __) => const ShimmerBox(),
              errorWidget: (_, __, ___) => const ImageFallback(),
            ),
    );
    if (semanticLabel != null) image = Semantics(image: true, label: semanticLabel, child: image);
    return aspectRatio == null ? image : AspectRatio(aspectRatio: aspectRatio!, child: image);
  }
}

class ImageFallback extends StatelessWidget {
  const ImageFallback({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      color: Theme.of(context).colorScheme.primaryContainer,
      alignment: Alignment.center,
      child: Icon(Icons.sports_score_rounded, size: 36, color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.5)),
    );
  }
}

/// Pulsing grey block used for loading skeletons (no extra package).
class ShimmerBox extends StatefulWidget {
  const ShimmerBox({super.key, this.height, this.width, this.radius = 0});

  final double? height;
  final double? width;
  final double radius;

  @override
  State<ShimmerBox> createState() => _ShimmerBoxState();
}

class _ShimmerBoxState extends State<ShimmerBox> with SingleTickerProviderStateMixin {
  late final AnimationController _controller =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 1100))..repeat(reverse: true);

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (_, __) => Container(
        height: widget.height,
        width: widget.width,
        decoration: BoxDecoration(
          color: Color.lerp(const Color(0xFFEDEDF3), const Color(0xFFF6F6FA), _controller.value),
          borderRadius: BorderRadius.circular(widget.radius),
        ),
      ),
    );
  }
}
