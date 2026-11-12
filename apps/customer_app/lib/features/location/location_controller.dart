import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/storage/preferences.dart';
import '../../shared/models/catalog.dart';
import '../../shared/repositories/profile_repository.dart';
import '../../shared/repositories/venue_repository.dart';
import 'location_service.dart';

class LocationState {
  const LocationState({this.city, this.point, this.access, this.locating = false});

  final City? city;
  final GeoPoint? point;

  /// Null until checked.
  final LocationAccess? access;
  final bool locating;

  bool get hasPoint => point != null;

  LocationState copyWith({
    Object? city = _keep,
    Object? point = _keep,
    Object? access = _keep,
    bool? locating,
  }) =>
      LocationState(
        city: identical(city, _keep) ? this.city : city as City?,
        point: identical(point, _keep) ? this.point : point as GeoPoint?,
        access: identical(access, _keep) ? this.access : access as LocationAccess?,
        locating: locating ?? this.locating,
      );

  static const Object _keep = Object();
}

/// Cities come from `GET /cities`; nothing is hard-coded in the app.
final citiesProvider = FutureProvider<List<City>>((ref) => ref.watch(venueRepositoryProvider).cities());

/// Selected city (manual, persisted) and device location (only if the user allows it).
/// The app is fully usable with a city alone.
class LocationController extends Notifier<LocationState> {
  @override
  LocationState build() {
    final prefs = ref.read(sharedPreferencesProvider);
    final id = prefs.getString(PrefKeys.cityId);
    final name = prefs.getString(PrefKeys.cityName);
    Future.microtask(_init);
    return LocationState(city: id != null && name != null ? City(id: id, name: name) : null);
  }

  Future<void> _init() async {
    // 1. Restore location silently if the user already granted it (no prompt on launch).
    try {
      final service = ref.read(locationServiceProvider);
      final access = await service.status();
      state = state.copyWith(access: access);
      if (access == LocationAccess.granted) {
        final point = await service.currentPoint();
        if (point != null) state = state.copyWith(point: point);
      }
    } catch (_) {
      // Location is optional.
    }
    // 2. Reconcile the stored city with the server's list / the saved preference.
    try {
      final cities = await ref.read(citiesProvider.future);
      final current = state.city;
      if (current != null) {
        final match = cities.where((c) => c.id == current.id);
        if (match.isEmpty) {
          await _persist(null);
          state = state.copyWith(city: null);
        } else {
          state = state.copyWith(city: match.first);
        }
        return;
      }
      final settings = await ref.read(profileRepositoryProvider).me();
      final preferred = cities.where((c) => c.id == settings.preferredCityId);
      if (preferred.isNotEmpty && state.city == null) {
        await _persist(preferred.first);
        state = state.copyWith(city: preferred.first);
      }
    } catch (_) {
      // Offline or not signed in yet: the user can pick a city manually.
    }
  }

  Future<void> _persist(City? city) async {
    final prefs = ref.read(sharedPreferencesProvider);
    if (city == null) {
      await prefs.remove(PrefKeys.cityId);
      await prefs.remove(PrefKeys.cityName);
    } else {
      await prefs.setString(PrefKeys.cityId, city.id);
      await prefs.setString(PrefKeys.cityName, city.name);
    }
  }

  Future<void> selectCity(City city) async {
    await _persist(city);
    state = state.copyWith(city: city);
    try {
      await ref.read(profileRepositoryProvider).setPreferredCity(city.id);
    } catch (_) {
      // Saving the preference is best-effort; the choice still applies on this device.
    }
  }

  /// Asks for permission (call from a user action only) and reads the position.
  Future<LocationAccess> useCurrentLocation() async {
    final service = ref.read(locationServiceProvider);
    state = state.copyWith(locating: true);
    try {
      final access = await service.request();
      state = state.copyWith(access: access);
      if (access == LocationAccess.granted) {
        final point = await service.currentPoint();
        state = state.copyWith(point: point);
        if (point == null) return LocationAccess.serviceDisabled;
      }
      return access;
    } finally {
      state = state.copyWith(locating: false);
    }
  }

  Future<void> openSettings() => ref.read(locationServiceProvider).openSettings();
}

final locationControllerProvider = NotifierProvider<LocationController, LocationState>(LocationController.new);
