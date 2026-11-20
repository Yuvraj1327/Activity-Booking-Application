import 'package:flutter/material.dart';

/// Sports that have a branded icon in `assets/icons/sports/` (keys match the API's `icon_key`).
const _sportAssets = {
  'cricket', 'football', 'badminton', 'tennis', 'basketball', 'volleyball', 'table_tennis', 'hockey',
  'squash', 'swimming', 'gym', 'running', 'yoga', 'golf', 'boxing',
};

/// Asset path of the branded icon for a category, or null when none exists (e.g. snooker).
String? sportIconAsset(String? iconKey, {String? slug}) {
  final key = (iconKey ?? slug)?.replaceAll('-', '_');
  return key != null && _sportAssets.contains(key) ? 'assets/icons/sports/$key.png' : null;
}

/// The sport's branded icon, or a Material icon for sports without one.
class SportIcon extends StatelessWidget {
  const SportIcon({super.key, this.iconKey, this.slug, this.size = 34, this.color});

  final String? iconKey;
  final String? slug;
  final double size;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final asset = sportIconAsset(iconKey, slug: slug);
    if (asset == null) {
      return Icon(categoryIcon(iconKey, slug: slug), size: size, color: color ?? Theme.of(context).colorScheme.primary);
    }
    return Image.asset(asset, width: size, height: size, fit: BoxFit.contain, excludeFromSemantics: true);
  }
}

/// Material fallback for sports that have no branded icon; unknown keys get a generic sports icon.
IconData categoryIcon(String? iconKey, {String? slug}) {
  switch (iconKey ?? slug) {
    case 'badminton':
    case 'tennis':
    case 'squash':
    case 'pickleball':
      return Icons.sports_tennis_rounded;
    case 'swimming':
      return Icons.pool_rounded;
    case 'gym':
      return Icons.fitness_center_rounded;
    case 'yoga':
      return Icons.self_improvement_rounded;
    case 'cricket':
      return Icons.sports_cricket_rounded;
    case 'football':
      return Icons.sports_soccer_rounded;
    case 'basketball':
      return Icons.sports_basketball_rounded;
    case 'table_tennis':
    case 'table-tennis':
      return Icons.sports_handball_rounded;
    case 'volleyball':
      return Icons.sports_volleyball_rounded;
    case 'hockey':
      return Icons.sports_hockey_rounded;
    case 'golf':
      return Icons.sports_golf_rounded;
    case 'boxing':
      return Icons.sports_mma_rounded;
    case 'running':
      return Icons.directions_run_rounded;
    case 'snooker':
      return Icons.sports_bar_rounded;
    default:
      return Icons.sports_rounded;
  }
}

IconData amenityIcon(String? iconKey, {String? slug}) {
  switch (iconKey ?? slug) {
    case 'parking':
      return Icons.local_parking_rounded;
    case 'changing_room':
    case 'changing-room':
      return Icons.checkroom_rounded;
    case 'shower':
      return Icons.shower_rounded;
    case 'water':
    case 'drinking-water':
      return Icons.water_drop_rounded;
    case 'floodlights':
      return Icons.light_rounded;
    case 'equipment':
    case 'equipment-rental':
      return Icons.sports_rounded;
    case 'first_aid':
    case 'first-aid':
      return Icons.medical_services_rounded;
    case 'cafe':
      return Icons.local_cafe_rounded;
    case 'wifi':
      return Icons.wifi_rounded;
    case 'lockers':
      return Icons.lock_rounded;
    case 'washroom':
      return Icons.wc_rounded;
    case 'ac':
    case 'air-conditioning':
      return Icons.ac_unit_rounded;
    default:
      return Icons.check_circle_outline_rounded;
  }
}
