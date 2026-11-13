import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';

import 'package:zuruv/core/constants/tokens.dart';
import 'package:zuruv/core/network/api_helpers.dart';
import 'package:zuruv/owner/core/utils/format.dart';
import 'package:zuruv/owner/shared/models/models.dart';
import 'package:zuruv/owner/shared/repositories/owner_repository.dart';
import 'package:zuruv/owner/shared/widgets/common_widgets.dart';

const defaultInterval = TimeInterval('06:00', '22:00');

/// Returns an error message when [intervals] are invalid (an interval that ends before it starts,
/// or two that overlap), otherwise null. Mirrors the server's rules for early feedback.
String? validateIntervals(List<TimeInterval> intervals) {
  final sorted = [...intervals]..sort((a, b) => a.opensAt.compareTo(b.opensAt));
  for (final i in sorted) {
    if (i.opensAt.substring(0, 5).compareTo(i.closesAt.substring(0, 5)) >= 0) return 'Opening time must be before closing time.';
  }
  for (var k = 1; k < sorted.length; k++) {
    if (sorted[k].opensAt.substring(0, 5).compareTo(sorted[k - 1].closesAt.substring(0, 5)) < 0) return 'Time ranges cannot overlap.';
  }
  return null;
}

/// The theme's buttons are full-width (infinite minimum width), which cannot sit inside a Row.
final _compactButton = OutlinedButton.styleFrom(minimumSize: const Size(0, 44));

/// Manage Slots: regular weekly hours and special dates (custom hours or closures).
/// Slot length and price belong to each court (see the Courts screen). Saving hours that would
/// invalidate an existing booking is refused by the server with the affected bookings listed.
class ManageSlotsScreen extends ConsumerStatefulWidget {
  const ManageSlotsScreen({super.key, required this.venueId});
  final String venueId;

  @override
  ConsumerState<ManageSlotsScreen> createState() => _ManageSlotsScreenState();
}

class _ManageSlotsScreenState extends ConsumerState<ManageSlotsScreen> {
  List<DayHours> _regular = [];
  List<SpecialDate> _special = [];
  String? _slotStatus;
  String? _slotMessage;
  bool _loading = true;
  bool _savingRegular = false;
  bool _savingSpecial = false;
  String? _loadError;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _loadError = null;
    });
    try {
      final s = await ref.read(ownerRepositoryProvider).schedule(widget.venueId);
      if (!mounted) return;
      setState(() {
        _regular = s.regular;
        _special = s.special;
        _slotStatus = s.slotStatus;
        _slotMessage = s.slotMessage;
        _loading = false;
      });
    } catch (e) {
      if (mounted) {
        setState(() {
          _loading = false;
          _loadError = errorMessage(e);
        });
      }
    }
  }

  void _toast(String m) => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));

  Future<String?> _pickTime(String initial) async {
    final parts = initial.split(':');
    final t = await showTimePicker(
      context: context,
      initialTime: TimeOfDay(hour: int.tryParse(parts[0]) ?? 6, minute: int.tryParse(parts[1]) ?? 0),
    );
    if (t == null) return null;
    return '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';
  }

  // ------------------------------------------------------------------ regular hours
  void _setDay(int weekday, List<TimeInterval> intervals) {
    setState(() => _regular = [for (final d in _regular) d.weekday == weekday ? DayHours(weekday, intervals) : d]);
  }

  Future<void> _editInterval(DayHours day, int index, {required bool opens}) async {
    final current = day.intervals[index];
    final picked = await _pickTime(opens ? current.opensAt : current.closesAt);
    if (picked == null) return;
    final next = [...day.intervals];
    next[index] = opens ? TimeInterval(picked, current.closesAt) : TimeInterval(current.opensAt, picked);
    _setDay(day.weekday, next);
  }

  Future<void> _saveRegular() async {
    for (final d in _regular) {
      final err = validateIntervals(d.intervals);
      if (err != null) {
        setState(() => _error = '${weekdayNames[d.weekday]}: $err');
        return;
      }
    }
    setState(() {
      _savingRegular = true;
      _error = null;
    });
    try {
      final s = await ref.read(ownerRepositoryProvider).saveSchedule(widget.venueId, regular: _regular);
      if (!mounted) return;
      setState(() => _regular = s.regular);
      _toast('Weekly hours saved');
    } catch (e) {
      if (mounted) setState(() => _error = errorMessage(e));
    } finally {
      if (mounted) setState(() => _savingRegular = false);
    }
  }

  // ------------------------------------------------------------------ special dates
  Future<void> _addSpecial() async {
    final result = await showModalBottomSheet<SpecialDate>(
      context: context,
      isScrollControlled: true,
      builder: (_) => const _SpecialDateSheet(),
    );
    if (result == null) return;
    if (_special.any((s) => s.onDate == result.onDate)) {
      setState(() => _error = 'There is already an entry for ${formatDate(DateTime.parse(result.onDate))}. Remove it first.');
      return;
    }
    setState(() {
      _error = null;
      _special = [..._special, result]..sort((a, b) => a.onDate.compareTo(b.onDate));
    });
  }

  Future<void> _saveSpecial() async {
    setState(() {
      _savingSpecial = true;
      _error = null;
    });
    try {
      final s = await ref.read(ownerRepositoryProvider).saveSchedule(widget.venueId, special: _special);
      if (!mounted) return;
      setState(() => _special = s.special);
      _toast('Special dates saved');
    } catch (e) {
      if (mounted) setState(() => _error = errorMessage(e));
    } finally {
      if (mounted) setState(() => _savingSpecial = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Manage slots'),
          bottom: const TabBar(tabs: [Tab(text: 'Weekly hours'), Tab(text: 'Special dates')]),
        ),
        body: _loading
            ? const LoadingView()
            : _loadError != null
                ? ErrorView(message: _loadError!, onRetry: _load)
                : ResponsivePage(
                    maxWidth: 640,
                    child: Column(
                      children: [
                        if (_error != null) Padding(padding: const EdgeInsets.only(top: 8), child: AuthBanner(message: _error!)),
                        Expanded(child: TabBarView(children: [_regularTab(context), _specialTab(context)])),
                      ],
                    ),
                  ),
      ),
    );
  }

  Widget _notice() => UnavailableCard(
        title: _slotStatus == 'configured' ? 'Slots follow your courts' : 'No bookable courts yet',
        message: _slotStatus == 'configured'
            ? 'Slots are created from these hours and each court\'s slot length. Changes that would affect existing bookings are refused.'
            : (_slotMessage ?? 'Add a court with a slot length and price (Venue > Courts) to start taking bookings.'),
        icon: Icons.info_outline_rounded,
      );

  Widget _regularTab(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.symmetric(vertical: 12),
      children: [
        _notice(),
        const SizedBox(height: Gap.md),
        for (final d in _regular) _DayCard(
          day: d,
          onToggle: (open) => _setDay(d.weekday, open ? const [defaultInterval] : const []),
          onEdit: (i, opens) => _editInterval(d, i, opens: opens),
          onAdd: d.intervals.length >= 5
              ? null
              : () {
                  final last = d.intervals.isEmpty ? null : d.intervals.last.closesAt;
                  final start = last == null || last.compareTo('21:00') >= 0 ? '06:00' : last.substring(0, 5);
                  _setDay(d.weekday, [...d.intervals, TimeInterval(start, '23:00')]);
                },
          onRemove: (i) => _setDay(d.weekday, [...d.intervals]..removeAt(i)),
        ),
        const SizedBox(height: Gap.lg),
        LoadingButton(label: 'Save weekly hours', loading: _savingRegular, onPressed: _saveRegular),
      ],
    );
  }

  Widget _specialTab(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.symmetric(vertical: 12),
      children: [
        Text('Holidays and days with different hours replace the weekly hours for that date.',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(color: ZuruvColors.textSecondary)),
        const SizedBox(height: Gap.md),
        if (_special.isEmpty)
          const UnavailableCard(title: 'No special dates', message: 'Add a holiday closure or custom hours for a date.', icon: Icons.event_outlined)
        else
          for (final s in _special)
            Card(
              margin: const EdgeInsets.only(bottom: Gap.md),
              child: ListTile(
                leading: Icon(s.isClosed ? Icons.event_busy_rounded : Icons.schedule_rounded),
                title: Text(formatDate(DateTime.parse(s.onDate)), style: const TextStyle(fontWeight: FontWeight.w700)),
                subtitle: Text([
                  s.isClosed ? 'Closed' : '${time12(s.opensAt!)} – ${time12(s.closesAt!)}',
                  if (s.note != null && s.note!.isNotEmpty) s.note!,
                ].join(' · ')),
                trailing: IconButton(
                  tooltip: 'Remove',
                  icon: const Icon(Icons.close_rounded),
                  onPressed: () => setState(() => _special = _special.where((x) => x.onDate != s.onDate).toList()),
                ),
              ),
            ),
        OutlinedButton.icon(onPressed: _addSpecial, icon: const Icon(Icons.add_rounded), label: const Text('Add special date')),
        const SizedBox(height: Gap.lg),
        LoadingButton(label: 'Save special dates', loading: _savingSpecial, onPressed: _saveSpecial),
      ],
    );
  }
}

class _DayCard extends StatelessWidget {
  const _DayCard({required this.day, required this.onToggle, required this.onEdit, required this.onAdd, required this.onRemove});
  final DayHours day;
  final ValueChanged<bool> onToggle;
  final void Function(int index, bool opens) onEdit;
  final VoidCallback? onAdd;
  final ValueChanged<int> onRemove;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: Gap.md),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(Gap.lg, Gap.sm, Gap.lg, Gap.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Expanded(child: Text(weekdayNames[day.weekday], style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16))),
              Text(day.isOpen ? 'Open' : 'Closed', style: const TextStyle(color: ZuruvColors.textSecondary)),
              Switch(key: ValueKey('open-${day.weekday}'), value: day.isOpen, onChanged: onToggle),
            ]),
            for (var i = 0; i < day.intervals.length; i++)
              Row(children: [
                OutlinedButton(key: ValueKey('opens-${day.weekday}-$i'), style: _compactButton, onPressed: () => onEdit(i, true), child: Text(time12(day.intervals[i].opensAt))),
                const Padding(padding: EdgeInsets.symmetric(horizontal: 8), child: Text('to')),
                OutlinedButton(key: ValueKey('closes-${day.weekday}-$i'), style: _compactButton, onPressed: () => onEdit(i, false), child: Text(time12(day.intervals[i].closesAt))),
                const Spacer(),
                if (day.intervals.length > 1) IconButton(tooltip: 'Remove range', icon: const Icon(Icons.remove_circle_outline_rounded), onPressed: () => onRemove(i)),
              ]),
            if (day.isOpen) TextButton.icon(onPressed: onAdd, icon: const Icon(Icons.add_rounded, size: 18), label: const Text('Add time range')),
          ],
        ),
      ),
    );
  }
}

class _SpecialDateSheet extends StatefulWidget {
  const _SpecialDateSheet();

  @override
  State<_SpecialDateSheet> createState() => _SpecialDateSheetState();
}

class _SpecialDateSheetState extends State<_SpecialDateSheet> {
  DateTime? _date;
  bool _closed = true;
  String _opens = '08:00';
  String _closes = '18:00';
  final _note = TextEditingController();
  String? _error;

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  Future<void> _pickDate() async {
    final now = DateTime.now();
    final d = await showDatePicker(context: context, initialDate: _date ?? now, firstDate: now, lastDate: now.add(const Duration(days: 730)));
    if (d != null) setState(() => _date = d);
  }

  Future<void> _pickTime(bool opens) async {
    final cur = (opens ? _opens : _closes).split(':');
    final t = await showTimePicker(context: context, initialTime: TimeOfDay(hour: int.parse(cur[0]), minute: int.parse(cur[1])));
    if (t == null) return;
    final v = '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';
    setState(() => opens ? _opens = v : _closes = v);
  }

  void _done() {
    if (_date == null) {
      setState(() => _error = 'Choose a date.');
      return;
    }
    if (!_closed && _opens.compareTo(_closes) >= 0) {
      setState(() => _error = 'Opening time must be before closing time.');
      return;
    }
    Navigator.pop(
      context,
      SpecialDate(
        onDate: apiDate(_date!),
        isClosed: _closed,
        opensAt: _closed ? null : _opens,
        closesAt: _closed ? null : _closes,
        note: _note.text.trim().isEmpty ? null : _note.text.trim(),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.fromLTRB(20, 4, 20, 20 + MediaQuery.of(context).viewInsets.bottom),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('Special date', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: Gap.md),
          OutlinedButton.icon(
            onPressed: _pickDate,
            icon: const Icon(Icons.event_rounded),
            label: Text(_date == null ? 'Choose date' : formatDate(_date!)),
          ),
          SwitchListTile(contentPadding: EdgeInsets.zero, title: const Text('Closed all day'), value: _closed, onChanged: (v) => setState(() => _closed = v)),
          if (!_closed)
            Row(children: [
              Expanded(child: OutlinedButton(onPressed: () => _pickTime(true), child: Text('Opens ${time12(_opens)}'))),
              const SizedBox(width: 8),
              Expanded(child: OutlinedButton(onPressed: () => _pickTime(false), child: Text('Closes ${time12(_closes)}'))),
            ]),
          const SizedBox(height: Gap.md),
          TextField(controller: _note, maxLength: 200, decoration: const InputDecoration(labelText: 'Note (optional)', hintText: 'e.g. Republic Day')),
          if (_error != null) Text(_error!, style: const TextStyle(color: ZuruvColors.error)),
          const SizedBox(height: Gap.md),
          FilledButton(onPressed: _done, child: const Text('Add')),
        ],
      ),
    );
  }
}
