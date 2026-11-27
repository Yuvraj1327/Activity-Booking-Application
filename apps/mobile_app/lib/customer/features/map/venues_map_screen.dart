import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';

import 'package:zuruv/core/maps/map_fallback.dart';
import 'package:zuruv/core/maps/maps_config.dart';
import 'package:zuruv/customer/core/utils/format.dart';
import 'package:zuruv/customer/features/discovery/venue_list_controller.dart';
import 'package:zuruv/customer/features/location/location_controller.dart';
import 'package:zuruv/customer/features/location/location_service.dart';
import 'package:zuruv/customer/features/venue_details/directions_launcher.dart';
import 'package:zuruv/customer/shared/models/venue.dart';

/// Map view of the venues matching the Explore filters (the same query as the list, so it also
/// covers "near me"). Venues without coordinates are simply not shown.
class VenuesMapScreen extends ConsumerStatefulWidget {
  const VenuesMapScreen({super.key, required this.query});

  final VenueQuery query;

  @override
  ConsumerState<VenuesMapScreen> createState() => _VenuesMapScreenState();
}

class _VenuesMapScreenState extends ConsumerState<VenuesMapScreen> {
  static const _fallbackCenter = LatLng(12.9716, 77.5946); // Bangalore

  GoogleMapController? _controller;
  VenueSummary? _selected;
  bool _fitted = false;

  @override
  void dispose() {
    _controller?.dispose();
    super.dispose();
  }

  List<VenueSummary> _mappable(VenueListState s) =>
      s.items.where((v) => v.latitude != null && v.longitude != null).toList();

  Future<void> _fit(List<VenueSummary> venues) async {
    final c = _controller;
    if (c == null || venues.isEmpty || _fitted) return;
    _fitted = true;
    final first = LatLng(venues.first.latitude!, venues.first.longitude!);
    if (venues.length == 1) return c.animateCamera(CameraUpdate.newLatLngZoom(first, 14));
    var south = first.latitude, north = first.latitude, west = first.longitude, east = first.longitude;
    for (final v in venues) {
      if (v.latitude! < south) south = v.latitude!;
      if (v.latitude! > north) north = v.latitude!;
      if (v.longitude! < west) west = v.longitude!;
      if (v.longitude! > east) east = v.longitude!;
    }
    await c.animateCamera(CameraUpdate.newLatLngBounds(
      LatLngBounds(southwest: LatLng(south, west), northeast: LatLng(north, east)),
      64,
    ));
  }

  Future<void> _myLocation() async {
    final messenger = ScaffoldMessenger.of(context);
    final controller = ref.read(locationControllerProvider.notifier);
    // Shows the system prompt if needed, then reads the position and updates shared state.
    final access = await controller.useCurrentLocation();
    if (!mounted) return;
    final point = ref.read(locationControllerProvider).point;
    if (access == LocationAccess.granted && point != null) {
      await _controller?.animateCamera(CameraUpdate.newLatLngZoom(LatLng(point.lat, point.lng), 13));
      return;
    }
    messenger.showSnackBar(SnackBar(
      content: Text(switch (access) {
        LocationAccess.serviceDisabled => 'Turn on location services to see your position.',
        LocationAccess.deniedForever => 'Location is blocked. Enable it in Settings.',
        LocationAccess.denied => 'Location permission was denied.',
        LocationAccess.granted => 'Could not get your position. Try again.',
      }),
      action: access == LocationAccess.deniedForever
          ? SnackBarAction(label: 'Settings', onPressed: controller.openSettings)
          : null,
    ));
  }

  @override
  Widget build(BuildContext context) {
    final available = ref.watch(mapsAvailableProvider);
    final state = ref.watch(venueListControllerProvider(widget.query));
    final location = ref.watch(locationControllerProvider);
    final venues = _mappable(state);

    return Scaffold(
      appBar: AppBar(title: const Text('Venues on map')),
      body: !available
          ? const Padding(
              padding: EdgeInsets.all(24),
              child: Center(child: MapFallback(message: 'Map view needs a Google Maps key. Use the list for now.')),
            )
          : state.loading && venues.isEmpty
              ? const Center(child: CircularProgressIndicator())
              : state.error != null && venues.isEmpty
                  ? Center(
                      child: Column(mainAxisSize: MainAxisSize.min, children: [
                        const Text('Could not load venues.'),
                        TextButton(
                          onPressed: () => ref.read(venueListControllerProvider(widget.query).notifier).refresh(),
                          child: const Text('Try again'),
                        ),
                      ]),
                    )
                  : Stack(children: [
                      GoogleMap(
                        initialCameraPosition: CameraPosition(
                          target: location.point == null ? _fallbackCenter : LatLng(location.point!.lat, location.point!.lng),
                          zoom: 12,
                        ),
                        onMapCreated: (c) {
                          _controller = c;
                          _fit(venues);
                        },
                        markers: {
                          for (final v in venues)
                            Marker(
                              markerId: MarkerId(v.id),
                              position: LatLng(v.latitude!, v.longitude!),
                              infoWindow: InfoWindow(title: v.name),
                              onTap: () => setState(() => _selected = v),
                            ),
                        },
                        onTap: (_) => setState(() => _selected = null),
                        myLocationEnabled: location.access == LocationAccess.granted,
                        myLocationButtonEnabled: false,
                        zoomControlsEnabled: false,
                        mapToolbarEnabled: false,
                      ),
                      if (venues.isEmpty)
                        const Positioned(
                          top: 12,
                          left: 16,
                          right: 16,
                          child: Card(
                            child: Padding(padding: EdgeInsets.all(12), child: Text('No venues with a map location match your filters.')),
                          ),
                        ),
                      Positioned(
                        right: 16,
                        bottom: _selected == null ? 24 : 190,
                        child: FloatingActionButton.small(
                          heroTag: 'venues-my-location',
                          tooltip: 'My location',
                          onPressed: _myLocation,
                          child: const Icon(Icons.my_location),
                        ),
                      ),
                      if (_selected != null)
                        Positioned(left: 16, right: 16, bottom: 16, child: _VenueCard(venue: _selected!)),
                    ]),
    );
  }
}

class _VenueCard extends ConsumerWidget {
  const _VenueCard({required this.venue});
  final VenueSummary venue;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final details = [
      if (venue.distanceKm != null) formatDistance(venue.distanceKm!),
      if (venue.startingPricePaise != null) 'from ${formatMoney(venue.startingPricePaise!, currency: venue.currency)}',
      if (venue.hasRating) '★ ${formatRating(venue.ratingAvg!)}',
    ].join('  ·  ');
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(venue.name, style: theme.textTheme.titleMedium),
          if (venue.addressLine != null) Text(venue.addressLine!, style: theme.textTheme.bodySmall),
          if (details.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 4), child: Text(details)),
          const SizedBox(height: 10),
          Row(children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: () async {
                  final messenger = ScaffoldMessenger.of(context);
                  final ok = await ref
                      .read(directionsLauncherProvider)
                      .open(latitude: venue.latitude!, longitude: venue.longitude!);
                  if (!ok) messenger.showSnackBar(const SnackBar(content: Text('Could not open maps on this device.')));
                },
                icon: const Icon(Icons.directions_outlined),
                label: const Text('Directions'),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(child: FilledButton(onPressed: () => context.push('/venues/${venue.id}'), child: const Text('View'))),
          ]),
        ]),
      ),
    );
  }
}
