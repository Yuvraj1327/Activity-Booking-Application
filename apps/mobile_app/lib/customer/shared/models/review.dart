/// A customer review of a venue (rating 1-5, optional comment) and the venue's reply, if any.
class Review {
  const Review({
    required this.id,
    required this.rating,
    required this.comment,
    required this.reviewerName,
    required this.createdAt,
    required this.replyBody,
  });

  factory Review.fromJson(Map<String, dynamic> j) {
    final reply = j['reply'] as Map<String, dynamic>?;
    return Review(
      id: j['id'] as String,
      rating: j['rating'] as int,
      comment: j['comment'] as String?,
      reviewerName: j['reviewer_name'] as String,
      createdAt: DateTime.parse(j['created_at'] as String),
      replyBody: reply?['body'] as String?,
    );
  }

  final String id;
  final int rating;
  final String? comment;
  final String reviewerName;
  final DateTime createdAt;
  final String? replyBody;
}

/// Average and count come from the server; the app never recomputes them.
class RatingSummary {
  const RatingSummary({required this.average, required this.count});

  factory RatingSummary.fromJson(Map<String, dynamic> j) =>
      RatingSummary(average: (j['average'] as num?)?.toDouble(), count: j['count'] as int);

  final double? average;
  final int count;
}

class ReviewPageData {
  const ReviewPageData({required this.items, required this.summary, required this.hasMore});

  factory ReviewPageData.fromJson(Map<String, dynamic> j) => ReviewPageData(
        items: [for (final r in j['items'] as List<dynamic>) Review.fromJson(r as Map<String, dynamic>)],
        summary: RatingSummary.fromJson(j['summary'] as Map<String, dynamic>),
        hasMore: j['has_more'] as bool,
      );

  final List<Review> items;
  final RatingSummary summary;
  final bool hasMore;
}
