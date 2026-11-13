/// Non-secret tunables for both roles. Nothing here is business data.
class AppConfig {
  const AppConfig._();

  static const int pageSize = 20;
  static const Duration searchDebounce = Duration(milliseconds: 400);

  /// Longest splash screen.
  static const Duration splashDuration = Duration(milliseconds: 1600);

  // ---- customer: discovery
  static const int homeSectionSize = 8;

  /// "Nearby" radius when the user shares their location.
  static const double nearbyRadiusKm = 25;

  /// Price filter slider (rupees per hour). The top stop means "no upper limit".
  static const int priceSliderMaxRupees = 5000;
  static const int priceSliderStepRupees = 100;

  // ---- owner: venue photos mirror the backend (`POST /owners/venues/{id}/images`): 5 MiB,
  // jpeg/png/webp, at most 10 per venue. The backend validates again; these only give early feedback.
  static const int venueImageMaxBytes = 5 * 1024 * 1024;
  static const int venueImageMaxCount = 10;
  static const Set<String> imageExtensions = {'jpg', 'jpeg', 'png', 'webp'};

  /// Avatar upload limits mirror the `profile-images` bucket (2 MiB; jpeg/png/webp).
  static const int avatarMaxBytes = 2 * 1024 * 1024;
  static const Set<String> avatarExtensions = {'jpg', 'jpeg', 'png', 'webp'};
}
