import 'package:flutter/material.dart';

import 'zuruv_colors.dart';
import 'zuruv_typography.dart';

/// The ZURUV theme in light (default) or dark appearance. In dark mode the brand [primary] is
/// replaced by a lighter violet so it stays readable on dark surfaces.
ThemeData buildZuruvTheme({required Color primary, Brightness brightness = Brightness.light}) {
  final dark = brightness == Brightness.dark;
  if (dark) primary = ZuruvColors.darkPrimary;
  final bg = dark ? ZuruvColors.darkBackground : ZuruvColors.background;
  final surface = dark ? ZuruvColors.darkSurface : ZuruvColors.surface;
  final border = dark ? ZuruvColors.darkBorder : ZuruvColors.border;
  final ink = dark ? ZuruvColors.darkText : ZuruvColors.text;
  final tint = dark ? ZuruvColors.darkPrimaryTint : ZuruvColors.primaryTint;
  final muted = dark ? ZuruvColors.darkTextSecondary : ZuruvColors.textSecondary;
  final scheme = ColorScheme.fromSeed(
    seedColor: primary,
    brightness: brightness,
  ).copyWith(
    primary: primary,
    onPrimary: dark ? ZuruvColors.darkBackground : Colors.white,
    primaryContainer: tint,
    onPrimaryContainer: primary,
    error: ZuruvColors.error,
    surface: surface,
    onSurface: ink,
    onSurfaceVariant: muted,
    outline: border,
  );

  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    scaffoldBackgroundColor: bg,
    textTheme: dark ? ZuruvTypography.darkTextTheme : ZuruvTypography.textTheme,
    appBarTheme: AppBarTheme(
      backgroundColor: surface,
      foregroundColor: ink,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      centerTitle: false,
    ),
    cardTheme: CardThemeData(
      color: surface,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: border),
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size.fromHeight(52),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size.fromHeight(52),
        side: BorderSide(color: border),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: surface,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: BorderSide(color: border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: BorderSide(color: border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: BorderSide(color: primary, width: 1.5),
      ),
    ),
    dividerTheme: DividerThemeData(color: border, space: 1),
  );
}
