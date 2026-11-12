import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';

import '../../core/utils/format.dart';
import '../../shared/models/models.dart';
import '../../shared/repositories/owner_repository.dart';
import '../../shared/widgets/common_widgets.dart';

/// Star filter: null = all reviews.
final reviewRatingFilterProvider = StateProvider.autoDispose<int?>((ref) => null);

final reviewsProvider = FutureProvider.autoDispose<OwnerReviewPage>(
  (ref) => ref.watch(ownerRepositoryProvider).reviews(rating: ref.watch(reviewRatingFilterProvider)),
);

/// Reviews customers left after a completed booking. The owner can reply once to each review.
class ReviewsScreen extends ConsumerWidget {
  const ReviewsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final data = ref.watch(reviewsProvider);
    final filter = ref.watch(reviewRatingFilterProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Reviews')),
      body: data.when(
        loading: () => const LoadingView(),
        error: (e, _) => ErrorView.fromError(e, onRetry: () => ref.invalidate(reviewsProvider)),
        data: (page) => RefreshIndicator(
          onRefresh: () async => ref.refresh(reviewsProvider.future),
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Text(
                page.summary.average == null
                    ? 'No ratings yet'
                    : '${page.summary.average!.toStringAsFixed(1)} average from ${page.summary.count} review${page.summary.count == 1 ? '' : 's'}',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                children: [
                  ChoiceChip(
                    label: Text('All (${page.summary.count})'),
                    selected: filter == null,
                    onSelected: (_) => ref.read(reviewRatingFilterProvider.notifier).state = null,
                  ),
                  for (final star in [5, 4, 3, 2, 1])
                    ChoiceChip(
                      label: Text('$star\u2605 (${page.summary.distribution[star] ?? 0})'),
                      selected: filter == star,
                      onSelected: (_) => ref.read(reviewRatingFilterProvider.notifier).state = star,
                    ),
                ],
              ),
              const SizedBox(height: 16),
              if (page.items.isEmpty)
                const EmptyState(
                  icon: Icons.rate_review_outlined,
                  title: 'No reviews yet',
                  message: 'Customers can review a booking after it has taken place. Their reviews will appear here.',
                )
              else
                for (final r in page.items) _ReviewCard(review: r),
            ],
          ),
        ),
      ),
    );
  }
}

class _ReviewCard extends ConsumerWidget {
  const _ReviewCard({required this.review});

  final OwnerReview review;

  Future<void> _reply(BuildContext context, WidgetRef ref) async {
    final controller = TextEditingController();
    final text = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Reply to review'),
        content: TextField(
          controller: controller,
          maxLines: 4,
          maxLength: 1000,
          decoration: const InputDecoration(hintText: 'Write a public reply'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(ctx).pop(), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.of(ctx).pop(controller.text.trim()), child: const Text('Post reply')),
        ],
      ),
    );
    controller.dispose();
    if (text == null || text.isEmpty) return;
    try {
      await ref.read(ownerRepositoryProvider).replyToReview(review.id, text);
      ref.invalidate(reviewsProvider);
    } catch (e) {
      if (context.mounted) {
        final message = e is ApiException ? e.message : 'Could not post your reply. Please try again.';
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
      }
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(child: Text(review.reviewerName, style: theme.textTheme.titleSmall)),
                Text(formatDate(review.createdAt.toLocal()), style: theme.textTheme.bodySmall),
              ],
            ),
            const SizedBox(height: 4),
            Row(
              children: [
                for (var i = 1; i <= 5; i++)
                  Icon(i <= review.rating ? Icons.star_rounded : Icons.star_outline_rounded, size: 18, color: const Color(0xFFFFB400)),
                const SizedBox(width: 8),
                Expanded(child: Text(review.venueName, style: theme.textTheme.bodySmall, overflow: TextOverflow.ellipsis)),
              ],
            ),
            if (review.comment != null) ...[
              const SizedBox(height: 8),
              Text(review.comment!),
            ],
            const SizedBox(height: 12),
            if (review.hasReply)
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(color: theme.colorScheme.surfaceContainerHighest, borderRadius: BorderRadius.circular(12)),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Your reply', style: theme.textTheme.labelMedium),
                    const SizedBox(height: 4),
                    Text(review.replyBody!),
                  ],
                ),
              )
            else
              OutlinedButton(onPressed: () => _reply(context, ref), child: const Text('Reply')),
          ],
        ),
      ),
    );
  }
}
