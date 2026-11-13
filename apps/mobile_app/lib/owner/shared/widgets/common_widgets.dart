import 'package:flutter/material.dart';
import 'package:flutter_shared/flutter_shared.dart';

import 'package:zuruv/core/constants/tokens.dart';

class SectionHeader extends StatelessWidget {
  const SectionHeader(this.title, {super.key, this.action, this.onAction});
  final String title;
  final String? action;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(0, Gap.xl, 0, Gap.md),
      child: Row(
        children: [
          Expanded(child: Text(title, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700))),
          if (action != null) TextButton(onPressed: onAction, child: Text(action!)),
        ],
      ),
    );
  }
}

class EmptyState extends StatelessWidget {
  const EmptyState({super.key, required this.icon, required this.title, required this.message, this.actionLabel, this.onAction});
  final IconData icon;
  final String title;
  final String message;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 84,
              height: 84,
              decoration: const BoxDecoration(color: ZuruvColors.primaryTint, shape: BoxShape.circle),
              child: Icon(icon, size: 38, color: theme.colorScheme.primary),
            ),
            const SizedBox(height: 18),
            Text(title, style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700), textAlign: TextAlign.center),
            const SizedBox(height: 8),
            Text(message, style: theme.textTheme.bodyMedium?.copyWith(color: ZuruvColors.textSecondary), textAlign: TextAlign.center),
            if (actionLabel != null) ...[
              const SizedBox(height: 20),
              FilledButton(onPressed: onAction, child: Text(actionLabel!)),
            ],
          ],
        ),
      ),
    );
  }
}

/// Shown where a number would go but the data does not exist yet. Says what it is waiting for;
/// never shows a placeholder figure.
class UnavailableCard extends StatelessWidget {
  const UnavailableCard({super.key, required this.title, required this.message, this.icon = Icons.hourglass_empty_rounded});
  final String title;
  final String message;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(Gap.lg),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(Radii.card),
        border: Border.all(color: ZuruvColors.border),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: ZuruvColors.textSecondary),
          const SizedBox(width: Gap.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: theme.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700)),
                const SizedBox(height: 4),
                Text(message, style: theme.textTheme.bodySmall?.copyWith(color: ZuruvColors.textSecondary)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// One headline metric. When [value] is null it renders an em dash plus the reason.
class StatTile extends StatelessWidget {
  const StatTile({super.key, required this.label, required this.icon, this.value, this.note});
  final String label;
  final IconData icon;
  final String? value;
  final String? note;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(Gap.lg),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(Radii.card),
        boxShadow: Shadows.card,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(color: ZuruvColors.primaryTint, borderRadius: BorderRadius.circular(10)),
              child: Icon(icon, size: 18, color: theme.colorScheme.primary),
            ),
            const SizedBox(width: 8),
            Expanded(child: Text(label, style: theme.textTheme.bodySmall?.copyWith(color: ZuruvColors.textSecondary), maxLines: 1, overflow: TextOverflow.ellipsis)),
          ]),
          const SizedBox(height: 12),
          Text(value ?? '—', style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800)),
          if (note != null) ...[
            const SizedBox(height: 4),
            Text(note!, style: theme.textTheme.bodySmall?.copyWith(color: ZuruvColors.textSecondary), maxLines: 2, overflow: TextOverflow.ellipsis),
          ],
        ],
      ),
    );
  }
}

class StatusChip extends StatelessWidget {
  const StatusChip(this.status, {super.key});
  final String status;

  @override
  Widget build(BuildContext context) {
    final (label, fg, bg) = switch (status) {
      'published' => ('Published', ZuruvColors.success, const Color(0xFFE6F7EE)),
      'draft' => ('Draft', const Color(0xFFB26A00), const Color(0xFFFFF3E0)),
      'archived' => ('Archived', ZuruvColors.textSecondary, const Color(0xFFF0F0F4)),
      _ => (status, ZuruvColors.textSecondary, const Color(0xFFF0F0F4)),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(20)),
      child: Text(label, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: fg)),
    );
  }
}

class RatingText extends StatelessWidget {
  const RatingText({super.key, required this.rating, required this.count});
  final double? rating;
  final int count;

  @override
  Widget build(BuildContext context) {
    final style = Theme.of(context).textTheme.bodySmall?.copyWith(color: ZuruvColors.textSecondary);
    if (rating == null || count == 0) return Text('No ratings yet', style: style);
    return Row(mainAxisSize: MainAxisSize.min, children: [
      const Icon(Icons.star_rounded, size: 16, color: Color(0xFFFFB400)),
      const SizedBox(width: 2),
      Text('${rating!.toStringAsFixed(1)} ($count)', style: style),
    ]);
  }
}

/// Page used by features that depend on a later step. Honest about why it is empty.
class PendingFeatureView extends StatelessWidget {
  const PendingFeatureView({super.key, required this.icon, required this.title, required this.message, this.dependsOn});
  final IconData icon;
  final String title;
  final String message;
  final String? dependsOn;

  @override
  Widget build(BuildContext context) {
    return EmptyState(
      icon: icon,
      title: title,
      message: dependsOn == null || dependsOn!.isEmpty ? message : '$message\n\nWaiting for: $dependsOn',
    );
  }
}
