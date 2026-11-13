import 'package:flutter/material.dart';

/// Maps the API's `icon_key` (falling back to the slug) to a Material icon. These are stand-ins
/// until the design team supplies a branded icon set; unknown keys get a generic sports icon.
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
