import 'package:flutter/material.dart';

import 'zuruv_colors.dart';

/// Typography scale. Uses the platform font (Roboto / SF); a brand font can be bundled later.
class ZuruvTypography {
  const ZuruvTypography._();

  static const TextTheme textTheme = TextTheme(
    headlineLarge: TextStyle(fontSize: 28, height: 1.25, fontWeight: FontWeight.w700, color: ZuruvColors.text),
    headlineMedium: TextStyle(fontSize: 24, height: 1.25, fontWeight: FontWeight.w700, color: ZuruvColors.text),
    titleLarge: TextStyle(fontSize: 20, height: 1.3, fontWeight: FontWeight.w600, color: ZuruvColors.text),
    titleMedium: TextStyle(fontSize: 16, height: 1.4, fontWeight: FontWeight.w600, color: ZuruvColors.text),
    bodyLarge: TextStyle(fontSize: 16, height: 1.5, color: ZuruvColors.text),
    bodyMedium: TextStyle(fontSize: 14, height: 1.5, color: ZuruvColors.text),
    bodySmall: TextStyle(fontSize: 12, height: 1.4, color: ZuruvColors.textSecondary),
    labelLarge: TextStyle(fontSize: 14, height: 1.2, fontWeight: FontWeight.w600),
  );
}
