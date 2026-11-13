import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';

import 'package:zuruv/core/network/api_helpers.dart';
import 'package:zuruv/customer/features/location/location_controller.dart';
import 'package:zuruv/customer/features/location/location_service.dart';

/// Explains why location did not turn on. Returns null when it worked.
String? locationMessage(LocationAccess access) => switch (access) {
      LocationAccess.granted => null,
      LocationAccess.denied => 'Location permission was denied. You can still choose your city manually.',
      LocationAccess.deniedForever =>
        'Location is blocked for ZURUV. Enable it in Settings, or choose your city manually.',
      LocationAccess.serviceDisabled => 'Location services are turned off on this device.',
    };

/// Asks for permission from a user action and tells them what happened.
Future<bool> enableLocation(BuildContext context, WidgetRef ref) async {
  final messenger = ScaffoldMessenger.of(context);
  final controller = ref.read(locationControllerProvider.notifier);
  final access = await controller.useCurrentLocation();
  final message = locationMessage(access);
  if (message == null) return ref.read(locationControllerProvider).hasPoint;
  messenger
    ..hideCurrentSnackBar()
    ..showSnackBar(
      SnackBar(
        content: Text(message),
        action: access == LocationAccess.deniedForever
            ? SnackBarAction(label: 'Settings', onPressed: controller.openSettings)
            : null,
      ),
    );
  return false;
}

Future<void> showCitySheet(BuildContext context) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    builder: (_) => const _CitySheet(),
  );
}

class _CitySheet extends ConsumerWidget {
  const _CitySheet();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final cities = ref.watch(citiesProvider);
    final location = ref.watch(locationControllerProvider);
    return ConstrainedBox(
      constraints: BoxConstraints(maxHeight: MediaQuery.sizeOf(context).height * 0.75),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 8),
            child: Text('Choose your city', style: theme.textTheme.titleLarge),
          ),
          ListTile(
            leading: location.locating
                ? const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.5))
                : Icon(Icons.my_location_rounded, color: theme.colorScheme.primary),
            title: const Text('Use my current location'),
            subtitle: Text(
              location.hasPoint ? 'On: showing distance and nearby venues' : 'Optional. Used only to show nearby venues.',
              style: theme.textTheme.bodySmall,
            ),
            onTap: location.locating ? null : () => enableLocation(context, ref),
          ),
          const Divider(),
          Flexible(
            child: cities.when(
              loading: () => const Padding(padding: EdgeInsets.all(32), child: LoadingView()),
              error: (e, _) => Padding(
                padding: const EdgeInsets.all(16),
                child: ErrorView(message: errorMessage(e), onRetry: () => ref.invalidate(citiesProvider)),
              ),
              data: (list) => list.isEmpty
                  ? const Padding(padding: EdgeInsets.all(32), child: Text('No cities are available yet.'))
                  : ListView.builder(
                      shrinkWrap: true,
                      itemCount: list.length,
                      itemBuilder: (context, i) {
                        final city = list[i];
                        final selected = location.city?.id == city.id;
                        return ListTile(
                          title: Text(city.name),
                          subtitle: city.state == null ? null : Text(city.state!),
                          trailing: selected ? Icon(Icons.check_circle_rounded, color: theme.colorScheme.primary) : null,
                          onTap: () async {
                            await ref.read(locationControllerProvider.notifier).selectCity(city);
                            if (context.mounted) Navigator.of(context).pop();
                          },
                        );
                      },
                    ),
            ),
          ),
          const SizedBox(height: 8),
        ],
      ),
    );
  }
}
