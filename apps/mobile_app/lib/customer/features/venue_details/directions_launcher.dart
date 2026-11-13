import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

/// Opens turn-by-turn directions to a venue in the device's maps app (or the browser).
/// No API key is involved: this is a plain Google Maps link built from the venue's coordinates.
abstract class DirectionsLauncher {
  Future<bool> open({required double latitude, required double longitude});
}

Uri directionsUri(double latitude, double longitude) => Uri.https('www.google.com', '/maps/dir/', {
      'api': '1',
      'destination': '$latitude,$longitude',
    });

class UrlDirectionsLauncher implements DirectionsLauncher {
  const UrlDirectionsLauncher();

  @override
  Future<bool> open({required double latitude, required double longitude}) async {
    try {
      return await launchUrl(directionsUri(latitude, longitude), mode: LaunchMode.externalApplication);
    } catch (_) {
      return false;
    }
  }
}

final directionsLauncherProvider = Provider<DirectionsLauncher>((ref) => const UrlDirectionsLauncher());
