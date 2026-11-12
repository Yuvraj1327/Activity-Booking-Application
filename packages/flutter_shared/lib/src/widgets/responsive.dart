import 'package:flutter/material.dart';

/// Width breakpoints (logical pixels).
class Breakpoints {
  const Breakpoints._();
  static const double compact = 600; // phones
  static const double medium = 840; // large phones / small tablets
}

enum ScreenSize { compact, medium, expanded }

ScreenSize screenSizeOf(BuildContext context) {
  final width = MediaQuery.sizeOf(context).width;
  if (width < Breakpoints.compact) return ScreenSize.compact;
  if (width < Breakpoints.medium) return ScreenSize.medium;
  return ScreenSize.expanded;
}

/// Centres content and caps its width on tablets, with page padding.
class ResponsivePage extends StatelessWidget {
  const ResponsivePage({super.key, required this.child, this.maxWidth = 640});

  final Widget child;
  final double maxWidth;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.topCenter,
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: maxWidth),
        child: Padding(padding: const EdgeInsets.symmetric(horizontal: 20), child: child),
      ),
    );
  }
}
