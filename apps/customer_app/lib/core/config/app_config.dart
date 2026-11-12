/// Non-secret tunables for discovery. Nothing here is venue data.
class AppConfig {
  const AppConfig._();

  static const int pageSize = 20;
  static const int homeSectionSize = 8;

  /// "Nearby" radius when the user shares their location.
  static const double nearbyRadiusKm = 25;

  /// Search typing delay before a request is sent.
  static const Duration searchDebounce = Duration(milliseconds: 400);

  /// Longest splash screen.
  static const Duration splashDuration = Duration(milliseconds: 1600);

  /// Price filter slider (rupees per hour). The top stop means "no upper limit".
  static const int priceSliderMaxRupees = 5000;
  static const int priceSliderStepRupees = 100;

  /// Avatar upload limits mirror the `profile-images` bucket (2 MiB; jpeg/png/webp).
  static const int avatarMaxBytes = 2 * 1024 * 1024;
  static const Set<String> avatarExtensions = {'jpg', 'jpeg', 'png', 'webp'};
}
