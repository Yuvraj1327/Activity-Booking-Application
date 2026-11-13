import 'package:flutter_test/flutter_test.dart';
import 'package:zuruv/customer/core/utils/format.dart';
import 'package:zuruv/customer/shared/models/booking.dart';
import 'package:zuruv/customer/shared/models/venue.dart';

void main() {
  bookingModelTests();
  group('formatMoney', () {
    test('formats paise with Indian grouping', () {
      expect(formatMoney(40000), '₹400');
      expect(formatMoney(123456700), '₹12,34,567');
      expect(formatMoney(49950), '₹499.50');
      expect(formatMoney(0), '₹0');
    });
    test('other currencies use western grouping', () {
      expect(formatMoney(123456700, currency: 'USD'), r'$1,234,567');
    });
  });

  test('formatDistance', () {
    expect(formatDistance(0.42), '420 m');
    expect(formatDistance(3.456), '3.5 km');
    expect(formatDistance(25.4), '25 km');
  });

  test('VenueSummary.fromJson reads the API shape', () {
    final v = VenueSummary.fromJson({
      'id': 'v1',
      'name': 'Ace Arena',
      'city_id': 'c1',
      'city_name': 'Bengaluru',
      'address_line': 'Koramangala',
      'latitude': 12.97,
      'longitude': 77.59,
      'cover_image_url': 'https://x/y.jpg',
      'categories': ['badminton'],
      'starting_price_paise': 40000,
      'currency': 'INR',
      'rating_avg': 4.5,
      'rating_count': 3,
      'distance_km': 1.25,
      'is_favorite': true,
    });
    expect(v.name, 'Ace Arena');
    expect(v.hasRating, isTrue);
    expect(v.isFavorite, isTrue);
    expect(v.distanceKm, 1.25);
    expect(VenueSummary.fromJson({'id': 'a', 'name': 'b', 'categories': <String>[]}).hasRating, isFalse);
  });

  test('VenueDetail falls back to the cover image for the gallery', () {
    final d = VenueDetail.fromJson({'id': 'v', 'name': 'n', 'cover_image_url': 'https://x/c.jpg', 'images': <dynamic>[]});
    expect(d.galleryUrls, ['https://x/c.jpg']);
  });

  group('VenueQuery', () {
    test('serialises only what is set', () {
      const q = VenueQuery(text: ' ace ', category: 'tennis', maxPricePaise: 90000, lat: 12.9, lng: 77.5, radiusKm: 25, sort: VenueSort.distance);
      expect(q.toParams(offset: 20), {
        'q': 'ace',
        'category': 'tennis',
        'max_price': 90000,
        'lat': 12.9,
        'lng': 77.5,
        'radius_km': 25.0,
        'sort': 'distance',
        'limit': 20,
        'offset': 20,
      });
      expect(const VenueQuery().toParams(offset: 0), {'sort': 'popular', 'limit': 20, 'offset': 0});
      expect(const VenueQuery(availableToday: true).toParams(offset: 0)['available_today'], true);
      expect(const VenueQuery(availableToday: true).hasFilters, isTrue);
    });

    test('is value-equal so it can key a provider family', () {
      expect(const VenueQuery(category: 'a'), const VenueQuery(category: 'a'));
      expect(const VenueQuery(category: 'a').hashCode, const VenueQuery(category: 'a').hashCode);
      expect(const VenueQuery(category: 'a') == const VenueQuery(category: 'b'), isFalse);
    });

    test('copyWith can clear a value', () {
      final q = const VenueQuery(category: 'a', minPricePaise: 10).copyWith(category: null);
      expect(q.category, isNull);
      expect(q.minPricePaise, 10);
    });
  });
}

// ---------------------------------------------------------------- booking models (Step 6)
void bookingModelTests() {
  group('booking models', () {
    test('availability parses courts, states and slots', () {
      final a = Availability.fromJson({
        'venue_id': 'v1',
        'date': '2030-01-07',
        'timezone': 'Asia/Kolkata',
        'closed_reason': null,
        'note': null,
        'resources': [
          {
            'resource_id': 'r1',
            'name': 'Court 1',
            'slot_minutes': 60,
            'slot_price_paise': 50000,
            'currency': 'INR',
            'state': 'available',
            'message': null,
            'slots': [
              {'starts_at': '2030-01-07T03:30:00Z', 'ends_at': '2030-01-07T04:30:00Z', 'local_start': '09:00', 'local_end': '10:00', 'price_paise': 50000},
            ],
          },
          {'resource_id': 'r2', 'name': 'Court 2', 'state': 'not_configured', 'currency': 'INR', 'slots': []},
        ],
      });
      expect(a.courts.length, 2);
      expect(a.courts[0].state, ResourceState.available);
      expect(a.courts[0].slots.single.localStart, '09:00');
      expect(a.courts[1].state, ResourceState.notConfigured);
      expect(a.hasAnySlot, isTrue);
    });

    test('booking parses status, labels and history', () {
      final b = Booking.fromJson({
        'id': 'b1',
        'booking_code': 'ZUR-AAAA1111',
        'status': 'pending_payment',
        'payment_status': 'unpaid',
        'venue_id': 'v1',
        'venue_name': 'Ace',
        'resource_name': 'Court 1',
        'booking_date': '2030-01-07',
        'starts_at': '2030-01-07T03:30:00Z',
        'ends_at': '2030-01-07T04:30:00Z',
        'local_start': '09:00',
        'local_end': '10:00',
        'duration_minutes': 60,
        'currency': 'INR',
        'total_amount_paise': 50000,
        'expires_at': '2030-01-07T03:00:00Z',
        'can_cancel': true,
        'history': [
          {'from_status': null, 'to_status': 'pending_payment', 'actor_role': 'customer', 'reason': null, 'created_at': '2030-01-01T00:00:00Z'},
        ],
      });
      expect(b.isHold, isTrue);
      expect(b.statusLabel, 'Awaiting payment');
      expect(b.history.single.toStatus, 'pending_payment');
      expect(statusLabelFor('cancelled_by_owner'), 'Cancelled by venue');
      expect(statusLabelFor('something_new'), 'something_new');
    });
  });
}
