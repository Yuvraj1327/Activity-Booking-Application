import 'package:flutter/material.dart';

/// Design tokens for the customer app (spacing, radii, shadows). Colours and type scale live in
/// flutter_shared (`ZuruvColors`, `ZuruvTypography`) so both apps stay consistent.
class Gap {
  const Gap._();
  static const double xs = 4;
  static const double sm = 8;
  static const double md = 12;
  static const double lg = 16;
  static const double xl = 20;
  static const double xxl = 24;
  static const double page = 20; // horizontal page padding
}

class Radii {
  const Radii._();
  static const double chip = 20;
  static const double button = 14;
  static const double card = 18;
  static const double image = 16;
  static const double sheet = 24;
}

class Shadows {
  const Shadows._();
  static const List<BoxShadow> card = [
    BoxShadow(color: Color(0x14141A33), blurRadius: 18, offset: Offset(0, 6)),
  ];
}
