/// Small date helpers (no intl dependency). The server owns all real date logic; these only
/// format values for display and build the date-picker strip.
const _months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const _weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

String apiDate(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

String weekdayShort(DateTime d) => _weekdays[d.weekday - 1];

String monthShort(DateTime d) => _months[d.month - 1];

/// "Sat, 14 Nov" from a yyyy-MM-dd string (the venue-local booking date).
String prettyDate(String yyyyMmDd) {
  final p = yyyyMmDd.split('-');
  if (p.length != 3) return yyyyMmDd;
  final d = DateTime(int.parse(p[0]), int.parse(p[1]), int.parse(p[2]));
  return '${weekdayShort(d)}, ${d.day} ${monthShort(d)}';
}

String prettyDuration(int minutes) {
  if (minutes < 60) return '$minutes min';
  final h = minutes ~/ 60;
  final m = minutes % 60;
  return m == 0 ? '$h hr' : '$h hr $m min';
}

/// Days from [from] (inclusive), used for the date strip.
List<DateTime> nextDays(DateTime from, int count) {
  final start = DateTime(from.year, from.month, from.day);
  return List.generate(count, (i) => DateTime(start.year, start.month, start.day + i));
}

/// "12 Nov, 18:30" in the device's local time.
String clockTime(DateTime t) {
  final h = t.hour.toString().padLeft(2, '0');
  final m = t.minute.toString().padLeft(2, '0');
  return '${t.day} ${monthShort(t)}, $h:$m';
}
