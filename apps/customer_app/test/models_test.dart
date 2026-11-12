import 'package:flutter_test/flutter_test.dart';
import 'package:zuruv_customer/core/utils/format.dart';
import 'package:zuruv_customer/shared/models/venue.dart';

void main() {
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
