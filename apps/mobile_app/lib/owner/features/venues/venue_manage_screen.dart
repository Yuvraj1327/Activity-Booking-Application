import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:go_router/go_router.dart';

import 'package:zuruv/core/constants/tokens.dart';
import 'package:zuruv/core/network/api_helpers.dart';
import 'package:zuruv/owner/core/utils/format.dart';
import 'package:zuruv/owner/shared/models/models.dart';
import 'package:zuruv/owner/shared/repositories/owner_repository.dart';
import 'package:zuruv/owner/shared/widgets/common_widgets.dart';
import 'package:zuruv/owner/shared/widgets/z_network_image.dart';
import 'package:zuruv/owner/features/venues/venues_screen.dart';

final venueDetailProvider = FutureProvider.autoDispose.family<OwnerVenueDetail, String>(
  (ref, id) => ref.watch(ownerRepositoryProvider).venue(id),
);

/// One venue: photos, summary, publish status and the actions (edit, hours, publish, delete).
class VenueManageScreen extends ConsumerStatefulWidget {
  const VenueManageScreen({super.key, required this.venueId});
  final String venueId;

  @override
  ConsumerState<VenueManageScreen> createState() => _VenueManageScreenState();
}

class _VenueManageScreenState extends ConsumerState<VenueManageScreen> {
  bool _busy = false;

  void _toast(String message) => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));

  Future<void> _run(Future<void> Function() action) async {
    setState(() => _busy = true);
    try {
      await action();
    } on ApiException catch (e) {
      final extra = e.details is List ? '\n${(e.details as List).join('\n')}' : '';
      _toast('${e.message}$extra');
    } catch (e) {
      _toast(errorMessage(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _togglePublish(OwnerVenueDetail v) => _run(() async {
        final repo = ref.read(ownerRepositoryProvider);
        if (v.card.isPublished || v.card.isPendingReview) {
          await repo.unpublish(v.id);
          _toast('Venue taken offline. It is now a draft.');
        } else {
          final after = await repo.publish(v.id);
          _toast(after.card.isPendingReview
              ? 'Venue submitted. It goes live once ZURUV approves it.'
              : 'Venue published. Customers can now find it.');
        }
        ref.invalidate(venueDetailProvider(widget.venueId));
        invalidateVenueData(ref);
      });

  Future<void> _delete(OwnerVenueDetail v) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete this venue?'),
        content: Text('"${v.name}" and its photos and hours will be removed permanently. This cannot be undone.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: TextButton.styleFrom(foregroundColor: ZuruvColors.error),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (ok != true) return;
    await _run(() async {
      await ref.read(ownerRepositoryProvider).deleteVenue(v.id);
      invalidateVenueData(ref);
      if (mounted) {
        context.pop();
        _toast('Venue deleted');
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final detail = ref.watch(venueDetailProvider(widget.venueId));
    return Scaffold(
      appBar: AppBar(title: const Text('Venue')),
      body: detail.when(
        loading: () => const LoadingView(),
        error: (e, _) => ErrorView.fromError(e, onRetry: () => ref.invalidate(venueDetailProvider(widget.venueId))),
        data: (v) => ResponsivePage(
          maxWidth: 720,
          child: ListView(
            padding: const EdgeInsets.only(bottom: 32),
            children: [
              _Gallery(images: v.images),
              const SizedBox(height: Gap.lg),
              Row(children: [
                Expanded(child: Text(v.name, style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800))),
                StatusChip(v.card.status),
              ]),
              const SizedBox(height: 6),
              Text(
                joinLocation(v.card.addressLine, v.card.cityName).isEmpty ? 'Location not set' : joinLocation(v.card.addressLine, v.card.cityName),
                style: const TextStyle(color: ZuruvColors.textSecondary),
              ),
              const SizedBox(height: 8),
              Row(children: [
                RatingText(rating: v.card.ratingAvg, count: v.card.ratingCount),
                const Spacer(),
                Text(
                  v.card.startingPricePaise == null ? 'Price not set' : 'From ${formatMoney(v.card.startingPricePaise!, currency: v.card.currency)}/hr',
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
              ]),
              if (v.card.categories.isNotEmpty) ...[
                const SizedBox(height: Gap.md),
                Wrap(spacing: 8, runSpacing: 6, children: [for (final c in v.card.categories) Chip(label: Text(c))]),
              ],
              if (!v.card.isPublished && v.publishBlockers.isNotEmpty) ...[
                const SizedBox(height: Gap.lg),
                _Blockers(blockers: v.publishBlockers),
              ],
              const SizedBox(height: Gap.lg),
              OutlinedButton.icon(
                onPressed: _busy ? null : () => context.push('/owner/venues/${v.id}/edit').then((_) {
                      ref.invalidate(venueDetailProvider(widget.venueId));
                    }),
                icon: const Icon(Icons.edit_rounded),
                label: const Text('Edit venue'),
              ),
              const SizedBox(height: Gap.md),
              OutlinedButton.icon(
                onPressed: _busy ? null : () => context.push('/owner/venues/${v.id}/courts'),
                icon: const Icon(Icons.sports_tennis_rounded),
                label: const Text('Courts & blocked times'),
              ),
              const SizedBox(height: Gap.md),
              OutlinedButton.icon(
                onPressed: _busy ? null : () => context.push('/owner/venues/${v.id}/slots'),
                icon: const Icon(Icons.schedule_rounded),
                label: const Text('Manage slots & hours'),
              ),
              const SizedBox(height: Gap.md),
              if (v.card.isSuspended)
                const Text('This venue was suspended by ZURUV. Contact support to have it reinstated.', style: TextStyle(fontWeight: FontWeight.w600))
              else ...[
                if (v.card.isPendingReview) const Padding(padding: EdgeInsets.only(bottom: 8), child: Text('Waiting for ZURUV approval. It is not visible to customers yet.')),
                LoadingButton(
                  label: v.card.isPublished ? 'Take offline' : (v.card.isPendingReview ? 'Withdraw submission' : 'Publish venue'),
                  loading: _busy,
                  onPressed: (!v.card.isPublished && !v.card.isPendingReview && !v.canPublish) ? null : () => _togglePublish(v),
                ),
              ],
              const SizedBox(height: Gap.lg),
              TextButton.icon(
                onPressed: _busy ? null : () => _delete(v),
                style: TextButton.styleFrom(foregroundColor: ZuruvColors.error),
                icon: const Icon(Icons.delete_outline_rounded),
                label: const Text('Delete venue'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Gallery extends StatelessWidget {
  const _Gallery({required this.images});
  final List<VenueImage> images;

  @override
  Widget build(BuildContext context) {
    if (images.isEmpty) {
      return const AspectRatio(aspectRatio: 16 / 9, child: ZNetworkImage(url: null, borderRadius: Radii.image));
    }
    return SizedBox(
      height: 200,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: images.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (_, i) => AspectRatio(
          aspectRatio: 4 / 3,
          child: ZNetworkImage(url: images[i].url, borderRadius: Radii.image, semanticLabel: images[i].altText),
        ),
      ),
    );
  }
}

class _Blockers extends StatelessWidget {
  const _Blockers({required this.blockers});
  final List<String> blockers;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(Gap.lg),
      decoration: BoxDecoration(color: const Color(0xFFFFF3E0), borderRadius: BorderRadius.circular(Radii.card)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Before you can publish', style: TextStyle(fontWeight: FontWeight.w800)),
          const SizedBox(height: 6),
          for (final b in blockers) Padding(padding: const EdgeInsets.only(top: 2), child: Text('• $b')),
        ],
      ),
    );
  }
}
