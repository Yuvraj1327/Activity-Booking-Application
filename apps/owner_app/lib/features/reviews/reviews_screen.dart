import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';

import '../../shared/models/models.dart';
import '../../shared/repositories/owner_repository.dart';
import '../../shared/widgets/common_widgets.dart';

final reviewsProvider = FutureProvider.autoDispose<PendingFeature>((ref) => ref.watch(ownerRepositoryProvider).reviews());

/// Reviews. There is no reviews table yet (customers can't review before they can book), so the
/// API reports the feature as pending. Owner replies are not offered until they are approved.
class ReviewsScreen extends ConsumerWidget {
  const ReviewsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final data = ref.watch(reviewsProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Reviews')),
      body: data.when(
        loading: () => const LoadingView(),
        error: (e, _) => ErrorView.fromError(e, onRetry: () => ref.invalidate(reviewsProvider)),
        data: (p) => PendingFeatureView(
          icon: Icons.rate_review_outlined,
          title: 'No reviews yet',
          message: p.message,
          dependsOn: p.dependsOn,
        ),
      ),
    );
  }
}
