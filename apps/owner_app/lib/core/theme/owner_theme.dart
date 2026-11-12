import 'package:flutter/material.dart';
import 'package:flutter_shared/flutter_shared.dart';

import '../constants/tokens.dart';

/// Shared ZURUV theme (violet primary, white surfaces) plus the Owner app's component styling.
ThemeData buildOwnerTheme() {
  const primary = ZuruvColors.ownerPrimary;
  final base = buildZuruvTheme(primary: primary);
  return base.copyWith(
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: Colors.white,
      surfaceTintColor: Colors.transparent,
      elevation: 8,
      height: 68,
      indicatorColor: ZuruvColors.primaryTint,
      labelTextStyle: WidgetStateProperty.resolveWith(
        (states) => TextStyle(
          fontSize: 11.5,
          fontWeight: states.contains(WidgetState.selected) ? FontWeight.w700 : FontWeight.w500,
          color: states.contains(WidgetState.selected) ? primary : ZuruvColors.textSecondary,
        ),
      ),
      iconTheme: WidgetStateProperty.resolveWith(
        (states) => IconThemeData(
          size: 24,
          color: states.contains(WidgetState.selected) ? primary : ZuruvColors.textSecondary,
        ),
      ),
    ),
    chipTheme: base.chipTheme.copyWith(
      backgroundColor: Colors.white,
      selectedColor: ZuruvColors.primaryTint,
      checkmarkColor: primary,
      side: const BorderSide(color: ZuruvColors.border),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(Radii.chip)),
      labelStyle: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: ZuruvColors.text),
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
    ),
    bottomSheetTheme: const BottomSheetThemeData(
      backgroundColor: Colors.white,
      surfaceTintColor: Colors.transparent,
      showDragHandle: true,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(Radii.sheet))),
    ),
  );
}
