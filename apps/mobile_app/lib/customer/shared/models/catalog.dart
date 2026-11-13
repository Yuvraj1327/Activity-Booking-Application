/// API models for catalogue data. Plain immutable classes with hand-written `fromJson` (no code
/// generation, so there is no build_runner step).
class City {
  const City({required this.id, required this.name, this.state});

  factory City.fromJson(Map<String, dynamic> json) =>
      City(id: json['id'] as String, name: json['name'] as String, state: json['state'] as String?);

  final String id;
  final String name;
  final String? state;

  @override
  bool operator ==(Object other) => other is City && other.id == id;

  @override
  int get hashCode => id.hashCode;
}

class VenueCategory {
  const VenueCategory({required this.id, required this.slug, required this.name, this.iconKey});

  factory VenueCategory.fromJson(Map<String, dynamic> json) => VenueCategory(
        id: json['id'] as String,
        slug: json['slug'] as String,
        name: json['name'] as String,
        iconKey: json['icon_key'] as String?,
      );

  final String id;
  final String slug;
  final String name;
  final String? iconKey;
}

class Amenity {
  const Amenity({required this.id, required this.slug, required this.name, this.iconKey});

  factory Amenity.fromJson(Map<String, dynamic> json) => Amenity(
        id: json['id'] as String,
        slug: json['slug'] as String,
        name: json['name'] as String,
        iconKey: json['icon_key'] as String?,
      );

  final String id;
  final String slug;
  final String name;
  final String? iconKey;
}
