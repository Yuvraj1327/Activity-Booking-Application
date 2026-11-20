import 'package:flutter/material.dart';
import 'package:flutter_shared/flutter_shared.dart';

import 'package:zuruv/core/constants/tokens.dart';

/// Shared ZURUV theme plus the customer app's component styling (bottom navigation, chips,
/// snack bars, page transitions).
ThemeData buildCustomerTheme({Brightness brightness = Brightness.light}) {
  final dark = brightness == Brightness.dark;
  final surface = dark ? ZuruvColors.darkSurface : Colors.white;
  final tint = dark ? ZuruvColors.darkPrimaryTint : ZuruvColors.customerTint;
  final muted = dark ? ZuruvColors.darkTextSecondary : ZuruvColors.textSecondary;
  final line = dark ? ZuruvColors.darkBorder : ZuruvColors.customerBorder;
  final ink = dark ? ZuruvColors.darkText : ZuruvColors.text;
  const primary = ZuruvColors.customerPrimary;
  final base = buildZuruvTheme(
    primary: primary,
    brightness: brightness,
    lightTint: ZuruvColors.customerTint,
    lightBorder: ZuruvColors.customerBorder,
  );
  final accent = base.colorScheme.primary;
  return base.copyWith(
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: surface,
      surfaceTintColor: Colors.transparent,
      elevation: 8,
      height: 68,
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
