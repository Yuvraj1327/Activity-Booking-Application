import 'package:flutter/material.dart';

import 'zuruv_colors.dart';
import 'zuruv_typography.dart';

/// Light theme only (dark mode is out of scope for the first release).
ThemeData buildZuruvTheme({required Color primary}) {
  final scheme = ColorScheme.fromSeed(
    seedColor: primary,
    brightness: Brightness.light,
  ).copyWith(
    primary: primary,
    onPrimary: Colors.white,
    primaryContainer: ZuruvColors.primaryTint,
    onPrimaryContainer: primary,
    error: ZuruvColors.error,
    surface: ZuruvColors.surface,
    onSurface: ZuruvColors.text,
    outline: ZuruvColors.border,
  );

  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    scaffoldBackgroundColor: ZuruvColors.background,
    textTheme: ZuruvTypography.textTheme,
    appBarTheme: const AppBarTheme(
      backgroundColor: ZuruvColors.surface,
      foregroundColor: ZuruvColors.text,
      elevation: 0,
      centerTitle: false,
    ),
    cardTheme: CardThemeData(
      color: ZuruvColors.surface,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: const BorderSide(color: ZuruvColors.border),
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
        side: const BorderSide(color: ZuruvColors.border),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: ZuruvColors.surface,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: ZuruvColors.border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: ZuruvColors.border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: BorderSide(color: primary, width: 1.5),
      ),
    ),
    dividerTheme: const DividerThemeData(color: ZuruvColors.border, space: 1),
  );
}
