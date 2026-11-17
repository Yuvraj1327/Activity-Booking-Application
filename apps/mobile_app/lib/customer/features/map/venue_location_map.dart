import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';

import 'package:zuruv/core/maps/maps_config.dart';

/// Small non-interactive-scroll map with a single venue marker (venue details page).
/// Renders nothing when maps are unavailable; the address and Directions button remain.
class VenueLocationMap extends ConsumerWidget {
  const VenueLocationMap({super.key, required this.name, required this.latitude, required this.longitude});

  final String name;
  final double latitude;
  final double longitude;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (!ref.watch(mapsAvailableProvider)) return const SizedBox.shrink();
    final target = LatLng(latitude, longitude);
    return Padding(
      padding: const EdgeInsets.only(top: 8, bottom: 4),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(12),
        child: SizedBox(
          height: 160,
          child: GoogleMap(
            initialCameraPosition: CameraPosition(target: target, zoom: 15),
            markers: {Marker(markerId: const MarkerId('venue'), position: target, infoWindow: InfoWindow(title: name))},
            // Lite mode (static image) is Android-only and keeps the page scroll smooth.
            liteModeEnabled: defaultTargetPlatform == TargetPlatform.android,
            zoomControlsEnabled: false,
            scrollGesturesEnabled: false,
            zoomGesturesEnabled: false,
            rotateGesturesEnabled: false,
            tiltGesturesEnabled: false,
            mapToolbarEnabled: false,
            myLocationButtonEnabled: false,
          ),
        ),
      ),
    );
  }
}
