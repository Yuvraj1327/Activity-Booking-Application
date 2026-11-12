/// Non-secret tunables for the Owner app. None of these are business data.
class AppConfig {
  const AppConfig._();

  static const int pageSize = 20;
  static const Duration searchDebounce = Duration(milliseconds: 400);
  static const Duration splashDuration = Duration(milliseconds: 1600);

  /// Venue photo limits mirror the backend (`POST /owners/venues/{id}/images`): 5 MiB, jpeg/png/webp,
  /// at most 10 per venue. The backend validates again; these only give early feedback.
  static const int venueImageMaxBytes = 5 * 1024 * 1024;
  static const int venueImageMaxCount = 10;
  static const Set<String> imageExtensions = {'jpg', 'jpeg', 'png', 'webp'};

  /// Avatar upload limits mirror the `profile-images` bucket (2 MiB; jpeg/png/webp).
  static const int avatarMaxBytes = 2 * 1024 * 1024;
  static const Set<String> avatarExtensions = {'jpg', 'jpeg', 'png', 'webp'};
}
