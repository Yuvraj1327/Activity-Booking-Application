import 'package:flutter_test/flutter_test.dart';
import 'package:zuruv/owner/core/utils/format.dart';
import 'package:zuruv/owner/features/schedules/manage_slots_screen.dart';
import 'package:zuruv/owner/shared/models/models.dart';

void main() {
  group('format', () {
    test('money uses Indian grouping and paise', () {
      expect(formatMoney(50000), '₹500');
      expect(formatMoney(123456700), '₹12,34,567');
      expect(formatMoney(150050), '₹1,500.50');
    });

    test('times', () {
      expect(time12('06:00:00'), '6:00 AM');
      expect(time12('00:30'), '12:30 AM');
      expect(time12('13:15'), '1:15 PM');
      expect(hhmm('06:00:00'), '06:00');
      expect(apiDate(DateTime(2030, 1, 6)), '2030-01-06');
    });

    test('timeAgo', () {
      final now = DateTime(2030, 1, 10, 12);
      expect(timeAgo(now.subtract(const Duration(seconds: 10)), now: now), 'Just now');
      expect(timeAgo(now.subtract(const Duration(minutes: 5)), now: now), '5 min ago');
      expect(timeAgo(now.subtract(const Duration(hours: 3)), now: now), '3 h ago');
      expect(timeAgo(now.subtract(const Duration(days: 2)), now: now), '2 d ago');
    });
  });

  group('schedule validation', () {
    test('accepts separate ranges', () {
      expect(validateIntervals(const [TimeInterval('06:00', '10:00'), TimeInterval('16:00', '22:00')]), isNull);
    });
    test('rejects reversed, equal and overlapping ranges', () {
      expect(validateIntervals(const [TimeInterval('10:00', '09:00')]), isNotNull);
      expect(validateIntervals(const [TimeInterval('10:00', '10:00')]), isNotNull);
      expect(validateIntervals(const [TimeInterval('06:00', '12:00'), TimeInterval('11:00', '14:00')]), isNotNull);
    });
    test('touching ranges are allowed', () {
      expect(validateIntervals(const [TimeInterval('06:00', '12:00'), TimeInterval('12:00', '14:00')]), isNull);
    });
    test('requests use HH:MM:SS', () {
      expect(const TimeInterval('06:00', '22:00').toJson(), {'opens_at': '06:00:00', 'closes_at': '22:00:00'});
      expect(const TimeInterval('06:00', '22:00'), const TimeInterval('06:00:00', '22:00:00'));
    });
  });

  group('requests', () {
    test('a draft sends only what is set', () {
      expect(const VenueDraft(name: 'Ace').toJson(), {'name': 'Ace'});
      expect(const VenueDraft(name: 'Ace', startingPricePaise: 50000, categoryIds: ['k1']).toJson(),
          {'name': 'Ace', 'starting_price_paise': 50000, 'category_ids': ['k1']});
    });

    test('cleared fields are sent as null', () {
      final json = const VenueDraft(name: 'Ace', clear: {'description', 'latitude', 'longitude'}).toJson();
      expect(json['description'], isNull);
      expect(json.containsKey('description'), isTrue);
      expect(json.containsKey('latitude'), isTrue);
    });

    test('special dates: closures carry no hours', () {
      expect(const SpecialDate(onDate: '2030-01-26', isClosed: true, note: 'Holiday').toJson(), {'on_date': '2030-01-26', 'is_closed': true, 'note': 'Holiday'});
      expect(const SpecialDate(onDate: '2030-02-01', isClosed: false, opensAt: '08:00', closesAt: '12:00').toJson(),
          {'on_date': '2030-02-01', 'is_closed': false, 'opens_at': '08:00:00', 'closes_at': '12:00:00'});
    });
  });

  group('parsing', () {
    test('venue detail', () {
      final d = OwnerVenueDetail.fromJson({
        'id': 'v1',
        'name': 'Ace',
        'status': 'draft',
        'city_name': 'Pune',
        'address_line': null,
        'cover_image_url': null,
        'image_count': 1,
        'categories': ['Tennis'],
        'starting_price_paise': 90000,
        'currency': 'INR',
        'rating_avg': null,
        'rating_count': 0,
        'updated_at': '2030-01-01T00:00:00Z',
        'description': null,
        'city_id': 'c1',
        'state': 'Maharashtra',
        'postal_code': null,
        'latitude': 18.5,
        'longitude': 73.8,
        'contact_phone': null,
        'timezone': 'Asia/Kolkata',
        'published_at': null,
        'category_details': [
          {'id': 'k2', 'slug': 'tennis', 'name': 'Tennis', 'icon_key': null, 'sort_order': 0}
        ],
        'amenities': [
          {'id': 'a1', 'slug': 'parking', 'name': 'Parking', 'icon_key': null}
        ],
        'images': [
          {'id': 'i1', 'url': 'https://x/y.jpg', 'alt_text': null, 'is_cover': true, 'sort_order': 0}
        ],
        'publish_blockers': ['Choose a city.'],
      });
      expect(d.categoryIds, ['k2']);
      expect(d.amenityIds, ['a1']);
      expect(d.images.single.isCover, isTrue);
      expect(d.latitude, 18.5);
      expect(d.canPublish, isFalse);
      expect(d.card.ratingAvg, isNull);
    });

    test('dashboard keeps unavailable metrics unavailable', () {
      const u = {'available': false, 'depends_on': 'Step 6', 'message': 'Later.'};
      final d = Dashboard.fromJson({
        'venues_total': 0,
        'venues_published': 0,
        'venues_draft': 0,
        'venues_archived': 0,
        'average_rating': null,
        'ratings_count': 0,
        'venue_performance': <dynamic>[],
        'recent_activity': <dynamic>[],
        'total_bookings': 5,
        'total_revenue': u,
        'monthly_revenue': u,
        'booking_overview': {'upcoming': 2, 'completed': 2, 'cancelled': 1},
        'average_utilization': u,
      });
      expect(d.averageRating, isNull);
      expect(d.totalBookings, 5);
      expect(d.bookingOverview.upcoming, 2);
      expect(d.totalRevenue.dependsOn, 'Step 6');
    });

    test('schedule', () {
      final s = VenueSchedule.fromJson({
        'regular': [
          {
            'weekday': 0,
            'intervals': [
              {'opens_at': '06:00:00', 'closes_at': '22:00:00'}
            ]
          },
          {'weekday': 1, 'intervals': <dynamic>[]},
        ],
        'special': [
          {'on_date': '2030-01-26', 'is_closed': true, 'opens_at': null, 'closes_at': null, 'note': 'Holiday'}
        ],
        'slot_configuration': {'status': 'not_configured', 'message': 'Add a court.'},
      });
      expect(s.regular.first.isOpen, isTrue);
      expect(s.regular[1].isOpen, isFalse);
      expect(s.special.single.isClosed, isTrue);
      expect(s.slotStatus, 'not_configured');
    });
  });
}
