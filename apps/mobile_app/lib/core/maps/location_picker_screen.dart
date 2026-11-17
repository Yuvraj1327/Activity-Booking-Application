import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';

import 'package:zuruv/core/maps/map_fallback.dart';
import 'package:zuruv/core/maps/maps_config.dart';
import 'package:zuruv/customer/features/location/location_service.dart';

/// Full-screen map where the user pans under a centre pin and confirms a location.
/// Pops with the chosen [GeoPoint], or null when cancelled.
Future<GeoPoint?> pickLocationOnMap(BuildContext context, {GeoPoint? initial}) =>
    Navigator.of(context).push<GeoPoint>(MaterialPageRoute(builder: (_) => LocationPickerScreen(initial: initial)));

class LocationPickerScreen extends ConsumerStatefulWidget {
  const LocationPickerScreen({super.key, this.initial});

  final GeoPoint? initial;

  @override
  ConsumerState<LocationPickerScreen> createState() => _LocationPickerScreenState();
}

class _LocationPickerScreenState extends ConsumerState<LocationPickerScreen> {
  // Centre of India, zoomed out, when we know nothing else.
  static const _fallbackCenter = LatLng(20.5937, 78.9629);

  GoogleMapController? _controller;
  late LatLng _center;
  bool _myLocationEnabled = false;
  bool _locating = false;

  @override
  void initState() {
    super.initState();
    final i = widget.initial;
    _center = i == null ? _fallbackCenter : LatLng(i.lat, i.lng);
    _checkPermission();
  }

  @override
  void dispose() {
    _controller?.dispose();
    super.dispose();
  }

  Future<void> _checkPermission() async {
    final access = await ref.read(locationServiceProvider).status();
    if (mounted) setState(() => _myLocationEnabled = access == LocationAccess.granted);
  }

  Future<void> _useMyLocation() async {
    final messenger = ScaffoldMessenger.of(context);
    final service = ref.read(locationServiceProvider);
    setState(() => _locating = true);
    final access = await service.request();
    if (!mounted) return;
    if (access != LocationAccess.granted) {
      setState(() => _locating = false);
      messenger.showSnackBar(SnackBar(
        content: Text(switch (access) {
          LocationAccess.serviceDisabled => 'Turn on location services to use your position.',
          LocationAccess.deniedForever => 'Location is blocked. Enable it in Settings.',
          _ => 'Location permission was denied.',
        }),
        action: access == LocationAccess.deniedForever
            ? SnackBarAction(label: 'Settings', onPressed: service.openSettings)
            : null,
      ));
      return;
    }
    final point = await service.currentPoint();
    if (!mounted) return;
    setState(() {
      _locating = false;
      _myLocationEnabled = true;
    });
    if (point == null) {
      messenger.showSnackBar(const SnackBar(content: Text('Could not get your position. Try again.')));
      return;
    }
    await _controller?.animateCamera(CameraUpdate.newLatLngZoom(LatLng(point.lat, point.lng), 16));
  }

  @override
  Widget build(BuildContext context) {
    final available = ref.watch(mapsAvailableProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Pick location')),
      body: !available
          ? const Padding(
              padding: EdgeInsets.all(24),
              child: Center(child: MapFallback(message: 'Maps are not configured. Enter the coordinates manually.')),
            )
          : Stack(children: [
              GoogleMap(
                initialCameraPosition: CameraPosition(target: _center, zoom: widget.initial == null ? 4 : 16),
                onMapCreated: (c) => _controller = c,
                onCameraMove: (p) => _center = p.target,
                myLocationEnabled: _myLocationEnabled,
                myLocationButtonEnabled: false,
                zoomControlsEnabled: false,
                mapToolbarEnabled: false,
              ),
              // Centre pin; its tip sits on the map centre.
              const IgnorePointer(
                child: Center(
                  child: Padding(
                    padding: EdgeInsets.only(bottom: 36),
                    child: Icon(Icons.location_pin, size: 48, color: Colors.red),
                  ),
                ),
              ),
              Positioned(
                right: 16,
                bottom: 100,
                child: FloatingActionButton.small(
                  heroTag: 'picker-my-location',
                  tooltip: 'Use my location',
                  onPressed: _locating ? null : _useMyLocation,
                  child: _locating
                      ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.my_location),
                ),
              ),
            ]),
      bottomNavigationBar: available
          ? SafeArea(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: FilledButton(
                  onPressed: () => Navigator.of(context).pop(GeoPoint(_center.latitude, _center.longitude)),
                  child: const Text('Use this location'),
                ),
              ),
            )
          : null,
    );
  }
}
