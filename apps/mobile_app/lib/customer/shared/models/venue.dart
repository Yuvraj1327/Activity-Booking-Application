import 'package:zuruv/customer/shared/models/catalog.dart';

double? _d(Object? v) => (v as num?)?.toDouble();

class VenueImage {
  const VenueImage({required this.id, this.url, this.altText, this.isCover = false, this.width, this.height});

  factory VenueImage.fromJson(Map<String, dynamic> json) => VenueImage(
        id: json['id'] as String,
        url: json['url'] as String?,
        altText: json['alt_text'] as String?,
        isCover: json['is_cover'] as bool? ?? false,
        width: json['width'] as int?,
        height: json['height'] as int?,
      );

  final String id;
  final String? url;
  final String? altText;
  final bool isCover;
  final int? width;
  final int? height;
}

/// A venue as shown in lists (home, explore, favorites).
class VenueSummary {
  const VenueSummary({
    required this.id,
    required this.name,
    this.cityId,
    this.cityName,
    this.addressLine,
    this.latitude,
    this.longitude,
    this.coverImageUrl,
    this.categories = const [],
    this.startingPricePaise,
    this.currency = 'INR',
    this.ratingAvg,
    this.ratingCount = 0,
    this.distanceKm,
    this.isFavorite = false,
  });

  factory VenueSummary.fromJson(Map<String, dynamic> json) => VenueSummary(
        id: json['id'] as String,
        name: json['name'] as String,
        cityId: json['city_id'] as String?,
        cityName: json['city_name'] as String?,
        addressLine: json['address_line'] as String?,
        latitude: _d(json['latitude']),
        longitude: _d(json['longitude']),
        coverImageUrl: json['cover_image_url'] as String?,
        categories: (json['categories'] as List<dynamic>? ?? const []).cast<String>(),
        startingPricePaise: json['starting_price_paise'] as int?,
        currency: json['currency'] as String? ?? 'INR',
        ratingAvg: _d(json['rating_avg']),
        ratingCount: json['rating_count'] as int? ?? 0,
        distanceKm: _d(json['distance_km']),
        isFavorite: json['is_favorite'] as bool? ?? false,
      );

  final String id;
  final String name;
  final String? cityId;
  final String? cityName;
  final String? addressLine;
  final double? latitude;
  final double? longitude;
  final String? coverImageUrl;
  final List<String> categories;
  final int? startingPricePaise;
  final String currency;
  final double? ratingAvg;
  final int ratingCount;
  final double? distanceKm;
  final bool isFavorite;

  bool get hasRating => ratingAvg != null && ratingCount > 0;
}

class VenueDetail extends VenueSummary {
  const VenueDetail({
    required super.id,
    required super.name,
    super.cityId,
    super.cityName,
    super.addressLine,
    super.latitude,
    super.longitude,
    super.coverImageUrl,
    super.categories,
    super.startingPricePaise,
    super.currency,
    super.ratingAvg,
    super.ratingCount,
    super.distanceKm,
    super.isFavorite,
    this.description,
    this.postalCode,
    this.contactPhone,
    this.timezone = 'Asia/Kolkata',
    this.categoryDetails = const [],
    this.amenities = const [],
    this.images = const [],
  });

  factory VenueDetail.fromJson(Map<String, dynamic> json) {
    final base = VenueSummary.fromJson(json);
    return VenueDetail(
      id: base.id,
      name: base.name,
      cityId: base.cityId,
      cityName: base.cityName,
      addressLine: base.addressLine,
      latitude: base.latitude,
      longitude: base.longitude,
      coverImageUrl: base.coverImageUrl,
      categories: base.categories,
      startingPricePaise: base.startingPricePaise,
      currency: base.currency,
      ratingAvg: base.ratingAvg,
      ratingCount: base.ratingCount,
      distanceKm: base.distanceKm,
      isFavorite: base.isFavorite,
      description: json['description'] as String?,
      postalCode: json['postal_code'] as String?,
      contactPhone: json['contact_phone'] as String?,
      timezone: json['timezone'] as String? ?? 'Asia/Kolkata',
      categoryDetails: (json['category_details'] as List<dynamic>? ?? const [])
          .map((e) => VenueCategory.fromJson(e as Map<String, dynamic>))
          .toList(),
      amenities: (json['amenities'] as List<dynamic>? ?? const [])
          .map((e) => Amenity.fromJson(e as Map<String, dynamic>))
          .toList(),
      images: (json['images'] as List<dynamic>? ?? const [])
          .map((e) => VenueImage.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }

  final String? description;
  final String? postalCode;
  final String? contactPhone;
  final String timezone;
  final List<VenueCategory> categoryDetails;
  final List<Amenity> amenities;
  final List<VenueImage> images;

  /// Gallery URLs, falling back to the cover image when no gallery exists.
  List<String> get galleryUrls {
    final urls = images.map((i) => i.url).whereType<String>().toList();
    if (urls.isEmpty && coverImageUrl != null) return [coverImageUrl!];
    return urls;
  }
}

class VenuePageData {
  const VenuePageData({required this.items, required this.hasMore});

  factory VenuePageData.fromJson(Map<String, dynamic> json) => VenuePageData(
        items: (json['items'] as List<dynamic>)
            .map((e) => VenueSummary.fromJson(e as Map<String, dynamic>))
            .toList(),
        hasMore: json['has_more'] as bool? ?? false,
      );

  final List<VenueSummary> items;
  final bool hasMore;
}

/// Sort orders accepted by `GET /venues`.
enum VenueSort {
  popular('popular', 'Popular'),
  rating('rating', 'Top rated'),
  priceAsc('price_asc', 'Price: low to high'),
  priceDesc('price_desc', 'Price: high to low'),
  distance('distance', 'Distance'),
  newest('newest', 'Newest');

  const VenueSort(this.apiValue, this.label);
  final String apiValue;
  final String label;
}

/// Everything that identifies one list of venues. Value-equal so it can key a provider family.
class VenueQuery {
  const VenueQuery({
    this.text,
    this.category,
    this.cityId,
    this.minPricePaise,
    this.maxPricePaise,
    this.lat,
    this.lng,
    this.radiusKm,
    this.sort = VenueSort.popular,
    this.pageSize = 20,
    this.favoritesOnly = false,
    this.availableToday = false,
  });

  final String? text;
  final String? category;
  final String? cityId;
  final int? minPricePaise;
  final int? maxPricePaise;
  final double? lat;
  final double? lng;
  final double? radiusKm;
  final VenueSort sort;
  final int pageSize;
  final bool favoritesOnly;

  /// Only venues with a bookable slot left today (decided by the backend's slot engine).
  final bool availableToday;

  bool get hasFilters =>
      category != null || minPricePaise != null || maxPricePaise != null || radiusKm != null || availableToday;

  Map<String, dynamic> toParams({required int offset}) => {
        if (text != null && text!.trim().isNotEmpty) 'q': text!.trim(),
        if (category != null) 'category': category,
        if (cityId != null) 'city_id': cityId,
        if (minPricePaise != null) 'min_price': minPricePaise,
        if (maxPricePaise != null) 'max_price': maxPricePaise,
        if (lat != null && lng != null) ...{'lat': lat, 'lng': lng},
        if (radiusKm != null) 'radius_km': radiusKm,
        if (availableToday) 'available_today': true,
        'sort': sort.apiValue,
        'limit': pageSize,
        'offset': offset,
      };

  VenueQuery copyWith({
    Object? text = _keep,
    Object? category = _keep,
    Object? cityId = _keep,
    Object? minPricePaise = _keep,
    Object? maxPricePaise = _keep,
    Object? lat = _keep,
    Object? lng = _keep,
    Object? radiusKm = _keep,
    VenueSort? sort,
    int? pageSize,
    bool? favoritesOnly,
    bool? availableToday,
  }) {
    return VenueQuery(
      text: identical(text, _keep) ? this.text : text as String?,
      category: identical(category, _keep) ? this.category : category as String?,
      cityId: identical(cityId, _keep) ? this.cityId : cityId as String?,
      minPricePaise: identical(minPricePaise, _keep) ? this.minPricePaise : minPricePaise as int?,
      maxPricePaise: identical(maxPricePaise, _keep) ? this.maxPricePaise : maxPricePaise as int?,
      lat: identical(lat, _keep) ? this.lat : lat as double?,
      lng: identical(lng, _keep) ? this.lng : lng as double?,
      radiusKm: identical(radiusKm, _keep) ? this.radiusKm : radiusKm as double?,
      sort: sort ?? this.sort,
      pageSize: pageSize ?? this.pageSize,
      favoritesOnly: favoritesOnly ?? this.favoritesOnly,
      availableToday: availableToday ?? this.availableToday,
    );
  }

  static const Object _keep = Object();

  @override
  bool operator ==(Object other) =>
      other is VenueQuery &&
      other.text == text &&
      other.category == category &&
      other.cityId == cityId &&
      other.minPricePaise == minPricePaise &&
      other.maxPricePaise == maxPricePaise &&
      other.lat == lat &&
      other.lng == lng &&
      other.radiusKm == radiusKm &&
      other.sort == sort &&
      other.pageSize == pageSize &&
      other.favoritesOnly == favoritesOnly &&
      other.availableToday == availableToday;

  @override
  int get hashCode => Object.hash(
        text,
        category,
        cityId,
        minPricePaise,
        maxPricePaise,
        lat,
        lng,
        radiusKm,
        sort,
        pageSize,
        favoritesOnly,
        availableToday,
      );
}
