import 'package:flutter/material.dart';
import 'package:flutter_shared/flutter_shared.dart';

import 'package:zuruv/core/constants/tokens.dart';

/// Owner-app palette: professional blue on a cool white canvas. Local to the Owner app, the
/// customer and admin apps do not read it.
class OwnerColors {
  const OwnerColors._();
  static const Color blue = Color(0xFF1556E8);
  static const Color blueDeep = Color(0xFF0B3FB8);
  static const Color canvas = Color(0xFFF6F8FC);
  static const Color tint = Color(0xFFE9F0FF);
}

/// Shared ZURUV theme (violet primary, white surfaces) plus the Owner app's component styling.
ThemeData buildOwnerTheme({Brightness brightness = Brightness.light}) {
  final dark = brightness == Brightness.dark;
  final surface = dark ? ZuruvColors.darkSurface : Colors.white;
  final tint = dark ? ZuruvColors.darkPrimaryTint : OwnerColors.tint;
  final muted = dark ? ZuruvColors.darkTextSecondary : ZuruvColors.textSecondary;
  final line = dark ? ZuruvColors.darkBorder : ZuruvColors.border;
  final ink = dark ? ZuruvColors.darkText : ZuruvColors.text;
  final primary = dark ? const Color(0xFF6FA0FF) : OwnerColors.blue;
  final base = buildZuruvTheme(primary: primary, brightness: brightness);
  final accent = base.colorScheme.primary;
  return base.copyWith(
    colorScheme: base.colorScheme.copyWith(primaryContainer: tint),
    scaffoldBackgroundColor: dark ? ZuruvColors.darkBackground : OwnerColors.canvas,
    appBarTheme: base.appBarTheme.copyWith(
      backgroundColor: dark ? ZuruvColors.darkBackground : OwnerColors.canvas,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: false,
      titleTextStyle: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: ink, letterSpacing: -0.3),
    ),
    cardTheme: CardThemeData(
      color: surface,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(Radii.card), side: BorderSide(color: line)),
    ),
    floatingActionButtonTheme: FloatingActionButtonThemeData(
      backgroundColor: accent,
      foregroundColor: Colors.white,
      elevation: 3,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(28)),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: surface,
      surfaceTintColor: Colors.transparent,
      elevation: 12,
      shadowColor: const Color(0x33142A5C),
      height: 68,
      labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
      indicatorColor: tint,
      labelTextStyle: WidgetStateProperty.resolveWith(
        (states) => TextStyle(
          fontSize: 11.5,
          fontWeight: states.contains(WidgetState.selected) ? FontWeight.w700 : FontWeight.w500,
          color: states.contains(WidgetState.selected) ? accent : muted,
        ),
      ),
      iconTheme: WidgetStateProperty.resolveWith(
        (states) => IconThemeData(
          size: 24,
          color: states.contains(WidgetState.selected) ? accent : muted,
        ),
      ),
    ),
    chipTheme: base.chipTheme.copyWith(
      backgroundColor: surface,
      selectedColor: tint,
      checkmarkColor: accent,
      side: BorderSide(color: line),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(Radii.chip)),
      labelStyle: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: ink),
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
    ),
    bottomSheetTheme: BottomSheetThemeData(
      backgroundColor: surface,
      surfaceTintColor: Colors.transparent,
      showDragHandle: true,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(Radii.sheet))),
    ),
  );
}
