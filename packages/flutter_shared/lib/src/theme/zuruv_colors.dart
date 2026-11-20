import 'package:flutter/material.dart';

/// Brand colour tokens. Values were sampled from the UI reference boards and are
/// approximate: confirm exact values with the brand owner.
/// The two reference boards differ slightly in primary, so each app passes its own.
class ZuruvColors {
  const ZuruvColors._();

  static const Color customerPrimary = Color(0xFF0B4FD8);
  static const Color customerTint = Color(0xFFEAF2FF);
  static const Color customerBorder = Color(0xFFE0E8F6);
  static const Color ownerPrimary = Color(0xFF4B2AF9);
  static const Color primaryTint = Color(0xFFF5F1FF);

  static const Color success = Color(0xFF0CAF61);
  static const Color error = Color(0xFFFA1945);

  static const Color text = Color(0xFF14151A);
  static const Color textSecondary = Color(0xFF686B72);
  static const Color border = Color(0xFFE4E4EC);
  static const Color surface = Color(0xFFFFFFFF);
  static const Color background = Color(0xFFFFFFFF);

  // Dark appearance
  static const Color darkBackground = Color(0xFF0F1117);
  static const Color darkSurface = Color(0xFF181B23);
  static const Color darkBorder = Color(0xFF2C303B);
  static const Color darkText = Color(0xFFE8EAF0);
  static const Color darkTextSecondary = Color(0xFF9AA0AD);
  static const Color darkPrimaryTint = Color(0xFF26234D);
  static const Color darkPrimary = Color(0xFF9A8CFF);
}
