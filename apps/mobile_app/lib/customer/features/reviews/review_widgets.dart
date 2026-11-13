import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:zuruv/core/network/api_helpers.dart';
import 'package:zuruv/customer/shared/models/review.dart';
import 'package:zuruv/customer/shared/repositories/review_repository.dart';

const _starColor = Color(0xFFFFB400);

class StarRow extends StatelessWidget {
  const StarRow({super.key, required this.rating, this.size = 18});

  final int rating;
  final double size;

  @override
  Widget build(BuildContext context) => Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          for (var i = 1; i <= 5; i++)
            Icon(i <= rating ? Icons.star_rounded : Icons.star_outline_rounded, size: size, color: _starColor),
        ],
      );
}

/// "Reviews" block on the venue page: the server's average and count, then the latest reviews.
class VenueReviewsSection extends ConsumerWidget {
  const VenueReviewsSection({super.key, required this.venueId});

  final String venueId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final data = ref.watch(venueReviewsProvider(venueId));
    return data.when(
      loading: () => const Padding(padding: EdgeInsets.symmetric(vertical: 16), child: Center(child: CircularProgressIndicator())),
      error: (e, _) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Reviews', style: theme.textTheme.titleLarge),
          const SizedBox(height: 8),
          Text(errorMessage(e), style: theme.textTheme.bodySmall),
          TextButton(onPressed: () => ref.invalidate(venueReviewsProvider(venueId)), child: const Text('Try again')),
        ],
      ),
      data: (page) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Reviews', style: theme.textTheme.titleLarge),
          const SizedBox(height: 4),
          Text(
            page.summary.average == null
                ? 'Play here and be the first to leave a review.'
                : '${page.summary.average!.toStringAsFixed(1)} from ${page.summary.count} review${page.summary.count == 1 ? '' : 's'}',
            style: theme.textTheme.bodyMedium,
          ),
          const SizedBox(height: 12),
          for (final r in page.items) _ReviewTile(review: r),
        ],
      ),
    );
  }
}

class _ReviewTile extends StatelessWidget {
  const _ReviewTile({required this.review});

  final Review review;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Expanded(child: Text(review.reviewerName, style: theme.textTheme.titleSmall)),
            StarRow(rating: review.rating, size: 16),
          ]),
          if (review.comment != null) ...[
            const SizedBox(height: 4),
            Text(review.comment!),
          ],
          if (review.replyBody != null)
            Container(
              margin: const EdgeInsets.only(top: 8),
              padding: const EdgeInsets.all(12),
              width: double.infinity,
              decoration: BoxDecoration(color: theme.colorScheme.surfaceContainerHighest, borderRadius: BorderRadius.circular(12)),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Reply from the venue', style: theme.textTheme.labelMedium),
                  const SizedBox(height: 4),
                  Text(review.replyBody!),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

/// Shown on a completed booking: the customer's own review, or a button to write one.
class BookingReviewCard extends ConsumerWidget {
  const BookingReviewCard({super.key, required this.bookingId});

  final String bookingId;

  Future<void> _write(BuildContext context, WidgetRef ref) async {
    final result = await showDialog<({int rating, String comment})>(
      context: context,
      builder: (_) => const _ReviewDialog(),
    );
    if (result == null) return;
    try {
      await ref.read(reviewRepositoryProvider).submit(bookingId, rating: result.rating, comment: result.comment);
      ref.invalidate(myReviewProvider(bookingId));
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Thanks for your review.')));
      }
    } catch (e) {
      if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(errorMessage(e))));
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final mine = ref.watch(myReviewProvider(bookingId));
    return mine.when(
      loading: () => const SizedBox.shrink(),
      error: (_, __) => const SizedBox.shrink(),
      data: (review) {
        if (review == null) {
          return Padding(
            padding: const EdgeInsets.only(top: 24),
            child: OutlinedButton.icon(
              onPressed: () => _write(context, ref),
              icon: const Icon(Icons.star_outline_rounded),
              label: const Text('Rate your experience'),
            ),
          );
        }
        return Padding(
          padding: const EdgeInsets.only(top: 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Your review', style: theme.textTheme.titleMedium),
              const SizedBox(height: 4),
              StarRow(rating: review.rating),
              if (review.comment != null) ...[const SizedBox(height: 4), Text(review.comment!)],
              if (review.replyBody != null) ...[
                const SizedBox(height: 8),
                Text('Reply from the venue: ${review.replyBody!}', style: theme.textTheme.bodySmall),
              ],
            ],
          ),
        );
      },
    );
  }
}

class _ReviewDialog extends StatefulWidget {
  const _ReviewDialog();

  @override
  State<_ReviewDialog> createState() => _ReviewDialogState();
}

class _ReviewDialogState extends State<_ReviewDialog> {
  int _rating = 0;
  final _comment = TextEditingController();

  @override
  void dispose() {
    _comment.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Rate your experience'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              for (var i = 1; i <= 5; i++)
                IconButton(
                  tooltip: '$i star${i == 1 ? '' : 's'}',
                  onPressed: () => setState(() => _rating = i),
                  icon: Icon(i <= _rating ? Icons.star_rounded : Icons.star_outline_rounded, color: _starColor),
                ),
            ],
          ),
          TextField(
            controller: _comment,
            maxLines: 3,
            maxLength: 1000,
            decoration: const InputDecoration(hintText: 'Tell others about the venue (optional)'),
          ),
        ],
      ),
      actions: [
        TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Cancel')),
        FilledButton(
          onPressed: _rating == 0 ? null : () => Navigator.of(context).pop((rating: _rating, comment: _comment.text)),
          child: const Text('Submit'),
        ),
      ],
    );
  }
}
