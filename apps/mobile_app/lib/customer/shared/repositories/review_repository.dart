import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';

import 'package:zuruv/core/network/api_helpers.dart';
import 'package:zuruv/customer/shared/models/review.dart';

/// Reviews. Who may review (a completed booking, once) is enforced by the backend.
class ReviewRepository {
  ReviewRepository(this._dio);

  final Dio _dio;

  Future<ReviewPageData> venueReviews(String venueId, {int offset = 0, int limit = 20}) => apiCall(() async {
        final res = await _dio.get<Map<String, dynamic>>(
          '/venues/$venueId/reviews',
          queryParameters: {'limit': limit, 'offset': offset},
        );
        return ReviewPageData.fromJson(res.data!);
      });

  /// The customer's own review of a booking, or null when there is none yet.
  Future<Review?> myReview(String bookingId) => apiCall(() async {
        try {
          final res = await _dio.get<Map<String, dynamic>>('/bookings/$bookingId/review');
          return Review.fromJson(res.data!);
        } on DioException catch (e) {
          if (e.response?.statusCode == 404) return null;
          rethrow;
        }
      });

  Future<Review> submit(String bookingId, {required int rating, String? comment}) => apiCall(() async {
        final res = await _dio.post<Map<String, dynamic>>(
          '/bookings/$bookingId/review',
          data: {
            'rating': rating,
            if (comment != null && comment.trim().isNotEmpty) 'comment': comment.trim(),
          },
        );
        return Review.fromJson(res.data!);
      });
}

final reviewRepositoryProvider = Provider<ReviewRepository>((ref) => ReviewRepository(ref.watch(apiClientProvider)));

final venueReviewsProvider = FutureProvider.autoDispose.family<ReviewPageData, String>(
  (ref, venueId) => ref.watch(reviewRepositoryProvider).venueReviews(venueId),
);

final myReviewProvider = FutureProvider.autoDispose.family<Review?, String>(
  (ref, bookingId) => ref.watch(reviewRepositoryProvider).myReview(bookingId),
);
