/// Money is stored and transferred as integer minor units (paise).
String formatMoney(int minorUnits, {String currency = 'INR'}) {
  final symbol = switch (currency) {
    'INR' => '₹',
    'USD' => r'$',
    'EUR' => '€',
    'GBP' => '£',
    _ => '$currency ',
  };
  final major = minorUnits ~/ 100;
  final rest = minorUnits % 100;
  final grouped = _group(major, indian: currency == 'INR');
  return rest == 0 ? '$symbol$grouped' : '$symbol$grouped.${rest.toString().padLeft(2, '0')}';
}

/// Indian digit grouping for INR (12,34,567), western for everything else.
String _group(int value, {required bool indian}) {
  final s = value.toString();
  if (s.length <= 3) return s;
  final last3 = s.substring(s.length - 3);
  var rest = s.substring(0, s.length - 3);
  final parts = <String>[];
  final size = indian ? 2 : 3;
  while (rest.length > size) {
    parts.insert(0, rest.substring(rest.length - size));
    rest = rest.substring(0, rest.length - size);
  }
  if (rest.isNotEmpty) parts.insert(0, rest);
  return '${parts.join(',')},$last3';
}

String formatDistance(double km) => km < 1 ? '${(km * 1000).round()} m' : '${km.toStringAsFixed(km < 10 ? 1 : 0)} km';

String formatRating(double rating) => rating.toStringAsFixed(1);

/// "Koramangala, Bengaluru" from whatever parts exist.
String joinLocation(String? address, String? city) {
  final parts = [address, city].whereType<String>().map((e) => e.trim()).where((e) => e.isNotEmpty);
  return parts.join(', ');
}
