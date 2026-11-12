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

String formatRating(double rating) => rating.toStringAsFixed(1);

/// "Koramangala, Bengaluru" from whatever parts exist.
String joinLocation(String? address, String? city) {
  final parts = [address, city].whereType<String>().map((e) => e.trim()).where((e) => e.isNotEmpty);
  return parts.join(', ');
}

const weekdayNames = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const _months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/// "26 Jan 2030" from a DateTime (local calendar date).
String formatDate(DateTime d) => '${d.day} ${_months[d.month - 1]} ${d.year}';

/// API date: 2030-01-26.
String apiDate(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

/// "06:00:00" -> "06:00".
String hhmm(String apiTime) => apiTime.length >= 5 ? apiTime.substring(0, 5) : apiTime;

/// "06:00" -> "6:00 AM".
String time12(String apiTime) {
  final h = int.tryParse(apiTime.substring(0, 2)) ?? 0;
  final m = apiTime.length >= 5 ? apiTime.substring(3, 5) : '00';
  final suffix = h >= 12 ? 'PM' : 'AM';
  final h12 = h % 12 == 0 ? 12 : h % 12;
  return '$h12:$m $suffix';
}

/// "5 min ago", "3 h ago", "12 Mar 2030".
String timeAgo(DateTime when, {DateTime? now}) {
  final diff = (now ?? DateTime.now()).difference(when.toLocal());
  if (diff.inMinutes < 1) return 'Just now';
  if (diff.inMinutes < 60) return '${diff.inMinutes} min ago';
  if (diff.inHours < 24) return '${diff.inHours} h ago';
  if (diff.inDays < 7) return '${diff.inDays} d ago';
  return formatDate(when.toLocal());
}
