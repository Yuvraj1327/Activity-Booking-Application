import 'package:flutter/material.dart';

/// Shown where a map would be when maps are not configured or not supported on this platform.
class MapFallback extends StatelessWidget {
  const MapFallback({super.key, this.message = 'Map is not available on this device.', this.height});

  final String message;
  final double? height;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      height: height,
      alignment: Alignment.center,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        Icon(Icons.map_outlined, size: 32, color: theme.colorScheme.outline),
        const SizedBox(height: 8),
        Text(message, textAlign: TextAlign.center, style: theme.textTheme.bodyMedium),
      ]),
    );
  }
}
