import 'package:flutter/material.dart';
import 'package:flutter_shared/flutter_shared.dart';

import 'package:zuruv/core/constants/tokens.dart';
import 'package:zuruv/core/theme/owner_theme.dart';

class SectionHeader extends StatelessWidget {
  const SectionHeader(this.title, {super.key, this.action, this.onAction});
  final String title;
  final String? action;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(0, Gap.xl, 0, Gap.sm),
      child: Row(
        children: [
          Expanded(child: Text(title, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800, letterSpacing: -0.2))),
          if (action != null)
            TextButton(
              onPressed: onAction,
              style: TextButton.styleFrom(visualDensity: VisualDensity.compact, textStyle: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13)),
              child: Text(action!),
            ),
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
              decoration: BoxDecoration(color: Theme.of(context).colorScheme.primaryContainer, shape: BoxShape.circle),
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
        color: Theme.of(context).colorScheme.surface,
        borderRadius: BorderRadius.circular(Radii.card),
        border: Border.all(color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.6)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          IconBadge(icon, size: 36, color: ZuruvColors.textSecondary),
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

/// White rounded card used across the Owner app: hairline border, soft shadow.
class OwnerCard extends StatelessWidget {
  const OwnerCard({super.key, required this.child, this.padding = const EdgeInsets.all(Gap.lg), this.onTap});
  final Widget child;
  final EdgeInsets padding;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Material(
      color: scheme.surface,
      borderRadius: BorderRadius.circular(Radii.card),
      child: Ink(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(Radii.card),
          border: Border.all(color: scheme.outline.withValues(alpha: 0.6)),
          boxShadow: Shadows.card,
        ),
        child: InkWell(
          borderRadius: BorderRadius.circular(Radii.card),
          onTap: onTap,
          child: Padding(padding: padding, child: child),
        ),
      ),
    );
  }
}

/// Small rounded square holding an icon, tinted with the brand blue.
class IconBadge extends StatelessWidget {
  const IconBadge(this.icon, {super.key, this.size = 38, this.color});
  final IconData icon;
  final double size;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final c = color ?? Theme.of(context).colorScheme.primary;
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(color: c.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(size * 0.32)),
      child: Icon(icon, size: size * 0.52, color: c),
    );
  }
}

/// Blue gradient headline card (total revenue / total earnings). When [value] is null it shows an
/// em dash and the [note], never a made-up figure.
class HeroStatCard extends StatelessWidget {
  const HeroStatCard({super.key, required this.label, required this.icon, this.value, this.note});
  final String label;
  final IconData icon;
  final String? value;
  final String? note;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(Gap.xl),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(22),
        gradient: const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [OwnerColors.blue, OwnerColors.blueDeep]),
        boxShadow: const [BoxShadow(color: Color(0x401556E8), blurRadius: 22, offset: Offset(0, 10))],
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: theme.textTheme.bodyMedium?.copyWith(color: Colors.white.withValues(alpha: 0.85), fontWeight: FontWeight.w600)),
                const SizedBox(height: 6),
                FittedBox(
                  fit: BoxFit.scaleDown,
                  alignment: Alignment.centerLeft,
                  child: Text(value ?? '—', style: theme.textTheme.headlineLarge?.copyWith(color: Colors.white, fontWeight: FontWeight.w800, letterSpacing: -0.5)),
                ),
                if (note != null) ...[
                  const SizedBox(height: 4),
                  Text(note!, style: theme.textTheme.bodySmall?.copyWith(color: Colors.white.withValues(alpha: 0.8))),
                ],
              ],
            ),
          ),
          const SizedBox(width: Gap.md),
          Container(
            width: 52,
            height: 52,
            decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.18), borderRadius: BorderRadius.circular(16)),
            child: Icon(icon, color: Colors.white, size: 28),
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
    return OwnerCard(
      padding: const EdgeInsets.all(Gap.md + 2),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(children: [
            IconBadge(icon, size: 34),
            const SizedBox(width: 8),
            Expanded(child: Text(label, style: theme.textTheme.bodySmall?.copyWith(color: ZuruvColors.textSecondary, fontWeight: FontWeight.w600), maxLines: 2, overflow: TextOverflow.ellipsis)),
          ]),
          const SizedBox(height: 10),
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Text(value ?? '—', style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800, letterSpacing: -0.3)),
          ),
          if (note != null) ...[
            const SizedBox(height: 2),
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
      'confirmed' => ('Confirmed', ZuruvColors.success, const Color(0xFFE6F7EE)),
      'pending' || 'pending_payment' => ('Pending', const Color(0xFFB26A00), const Color(0xFFFFF3E0)),
      'cancelled' => ('Cancelled', ZuruvColors.error, const Color(0xFFFDE8EC)),
      'completed' => ('Completed', OwnerColors.blue, OwnerColors.tint),
      _ => (status, ZuruvColors.textSecondary, const Color(0xFFF0F0F4)),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(20)),
      child: Text(label, maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: fg)),
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
    if (rating == null || count == 0) return Text('No ratings yet', style: style, maxLines: 1, overflow: TextOverflow.ellipsis);
    return Row(mainAxisSize: MainAxisSize.min, children: [
      const Icon(Icons.star_rounded, size: 16, color: Color(0xFFFFB400)),
      const SizedBox(width: 2),
      Flexible(child: Text('${rating!.toStringAsFixed(1)} ($count)', style: style, maxLines: 1, overflow: TextOverflow.ellipsis)),
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
