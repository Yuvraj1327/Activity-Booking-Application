import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:zuruv/customer/shared/models/review.dart';

import 'helpers.dart';

void main() {
  group('Review models', () {
    test('parse a review with and without a reply', () {
      final a = Review.fromJson({
        'id': 'r1',
        'rating': 5,
        'comment': 'Great',
        'reviewer_name': 'Priya S.',
        'created_at': '2030-01-01T10:00:00Z',
        'reply': {'body': 'Thanks', 'created_at': '2030-01-02T10:00:00Z'},
      });
      expect(a.replyBody, 'Thanks');
      final b = Review.fromJson({
        'id': 'r2',
        'rating': 2,
        'comment': null,
        'reviewer_name': 'Rahul V.',
        'created_at': '2030-01-01T10:00:00Z',
        'reply': null,
      });
      expect(b.comment, isNull);
      expect(b.replyBody, isNull);
    });

    test('page uses the server summary', () {
      final p = ReviewPageData.fromJson({
        'items': <dynamic>[],
        'summary': {'average': 4.5, 'count': 2, 'distribution': {'1': 0, '2': 0, '3': 0, '4': 1, '5': 1}},
        'limit': 20,
        'offset': 0,
        'has_more': false,
      });
      expect(p.summary.average, 4.5);
      expect(p.summary.count, 2);
    });
  });

  group('booking review', () {
    Future<TestEnv> openPastBooking(WidgetTester tester, {FakeReviewRepository? reviews}) async {
      final env = TestEnv(
        bookings: FakeBookingRepository(bookings: [bookingOf('b2', status: 'completed', venueName: 'Old Club')]),
        reviews: reviews,
      );
      await env.pump(tester);
      await tester.tap(inNavBar('Bookings'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Past'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Old Club'));
      await tester.pumpAndSettle();
      return env;
    }

    testWidgets('a completed booking can be rated once', (tester) async {
      final env = await openPastBooking(tester);
      await tester.scrollUntilVisible(find.text('Rate your experience'), 300);
      await tester.tap(find.text('Rate your experience'));
      await tester.pumpAndSettle();
      // Submit is disabled until a star is chosen.
      expect(tester.widget<FilledButton>(find.widgetWithText(FilledButton, 'Submit')).onPressed, isNull);
      await tester.tap(find.byTooltip('4 stars'));
      await tester.enterText(find.byType(TextField), 'Lovely courts');
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'Submit'));
      await tester.pumpAndSettle();
      expect(env.reviews.submitted, ['b2:4:Lovely courts']);
      expect(find.text('Your review'), findsOneWidget);
      expect(find.text('Rate your experience'), findsNothing);
    });

    testWidgets('an already reviewed booking shows the review, not the button', (tester) async {
      final reviews = FakeReviewRepository();
      reviews.mine['b2'] = Review(
        id: 'r', rating: 5, comment: 'Superb', reviewerName: 'Cathy C.', createdAt: DateTime(2030, 1, 1), replyBody: 'Thank you',
      );
      await openPastBooking(tester, reviews: reviews);
      await tester.scrollUntilVisible(find.text('Your review'), 300);
      expect(find.text('Superb'), findsOneWidget);
      expect(find.textContaining('Thank you'), findsOneWidget);
      expect(find.text('Rate your experience'), findsNothing);
    });
  });
}
