import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';

import 'package:zuruv/core/constants/tokens.dart';
import 'package:zuruv/core/network/api_helpers.dart';
import 'package:zuruv/owner/core/utils/format.dart';
import 'package:zuruv/owner/shared/models/models.dart';
import 'package:zuruv/owner/shared/repositories/owner_repository.dart';
import 'package:zuruv/owner/shared/widgets/common_widgets.dart';

/// Courts (bookable units with their own slot length and price) and temporary blocked times.
/// A court is only bookable once it has both a slot length and a price. Every change that would
/// invalidate a future booking is refused by the server and the affected bookings are named.
class CourtsScreen extends ConsumerStatefulWidget {
  const CourtsScreen({super.key, required this.venueId});
  final String venueId;

  @override
  ConsumerState<CourtsScreen> createState() => _CourtsScreenState();
}

class _CourtsScreenState extends ConsumerState<CourtsScreen> {
  List<Court> _courts = [];
  List<TimeBlock> _blocks = [];
  bool _loading = true;
  String? _loadError;
  String? _error;
  bool _busy = false;

  OwnerRepository get _repo => ref.read(ownerRepositoryProvider);

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
      final courts = await _repo.courts(widget.venueId);
      final blocks = await _repo.blocks(widget.venueId);
      if (!mounted) return;
      setState(() {
        _courts = courts;
        _blocks = blocks;
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

  Future<void> _run(Future<void> Function() action) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await action();
      await _load();
    } catch (e) {
      if (mounted) setState(() => _error = errorMessage(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _editCourt([Court? court]) async {
    final result = await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => _CourtSheet(court: court),
    );
    if (result == null) return;
    await _run(() async {
      await _repo.saveCourt(widget.venueId, courtId: court?.id, fields: result);
    });
  }

  Future<void> _toggleActive(Court c) => _run(() async {
        await _repo.saveCourt(widget.venueId, courtId: c.id, fields: {'is_active': !c.isActive});
      });

  Future<void> _deleteCourt(Court c) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: Text('Delete ${c.name}?'),
        content: const Text('Courts that have bookings cannot be deleted. Deactivate them instead.'),
        actions: [
          TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text('Keep')),
          FilledButton(onPressed: () => Navigator.of(context).pop(true), child: const Text('Delete')),
        ],
      ),
    );
    if (ok == true) await _run(() => _repo.deleteCourt(widget.venueId, c.id));
  }

  Future<void> _addBlock() async {
    final result = await showModalBottomSheet<_BlockInput>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => _BlockSheet(courts: _courts),
    );
    if (result == null) return;
    await _run(() async {
      await _repo.addBlock(widget.venueId, courtId: result.courtId, startsAt: result.start, endsAt: result.end, reason: result.reason);
    });
  }

  String _courtName(String? id) => id == null ? 'Whole venue' : _courts.where((c) => c.id == id).map((c) => c.name).firstOrNull ?? 'Court';

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Courts & blocked times')),
      body: _loading
          ? const LoadingView()
          : _loadError != null
              ? ErrorView(message: _loadError!, onRetry: _load)
              : ListView(
                  padding: const EdgeInsets.all(Gap.page),
                  children: [
                    if (_error != null) Padding(padding: const EdgeInsets.only(bottom: Gap.md), child: AuthBanner(message: _error!)),
                    Text('Courts', style: theme.textTheme.titleMedium),
                    const SizedBox(height: Gap.sm),
                    if (_courts.isEmpty)
                      const UnavailableCard(
                        title: 'No courts yet',
                        message: 'Add a court with a slot length and price so customers can book it.',
                        icon: Icons.sports_tennis_rounded,
                      )
                    else
                      for (final c in _courts)
                        Card(
                          margin: const EdgeInsets.only(bottom: Gap.md),
                          child: ListTile(
                            title: Text(c.name, style: const TextStyle(fontWeight: FontWeight.w700)),
                            subtitle: Text(c.configured
                                ? '${c.slotMinutes} min slots · ${formatMoney(c.slotPricePaise!)} per slot${c.isActive ? '' : ' · Inactive'}'
                                : 'Not open for booking: set a slot length and price'),
                            onTap: _busy ? null : () => _editCourt(c),
                            trailing: PopupMenuButton<String>(
                              tooltip: 'Court options',
                              onSelected: (v) => v == 'toggle' ? _toggleActive(c) : _deleteCourt(c),
                              itemBuilder: (_) => [
                                PopupMenuItem(value: 'toggle', child: Text(c.isActive ? 'Deactivate' : 'Activate')),
                                const PopupMenuItem(value: 'delete', child: Text('Delete')),
                              ],
                            ),
                          ),
                        ),
                    OutlinedButton.icon(onPressed: _busy ? null : () => _editCourt(), icon: const Icon(Icons.add_rounded), label: const Text('Add court')),
                    const SizedBox(height: Gap.xxl),
                    Text('Blocked times', style: theme.textTheme.titleMedium),
                    const SizedBox(height: 4),
                    Text('Block maintenance or private events. Customers cannot book blocked times.', style: theme.textTheme.bodySmall),
                    const SizedBox(height: Gap.sm),
                    if (_blocks.isEmpty)
                      const UnavailableCard(title: 'Nothing blocked', message: 'All open hours can be booked.', icon: Icons.event_available_rounded)
                    else
                      for (final b in _blocks)
                        Card(
                          margin: const EdgeInsets.only(bottom: Gap.md),
                          child: ListTile(
                            leading: const Icon(Icons.block_rounded),
                            title: Text(_courtName(b.courtId)),
                            subtitle: Text('${formatDate(b.startsAt.toLocal())} ${_clock(b.startsAt)}–${_clock(b.endsAt)}${b.reason == null ? '' : ' · ${b.reason}'}'),
                            trailing: IconButton(
                              tooltip: 'Remove block',
                              icon: const Icon(Icons.close_rounded),
                              onPressed: _busy ? null : () => _run(() => _repo.deleteBlock(widget.venueId, b.id)),
                            ),
                          ),
                        ),
                    OutlinedButton.icon(onPressed: _busy ? null : _addBlock, icon: const Icon(Icons.add_rounded), label: const Text('Block a time')),
                  ],
                ),
    );
  }

  static String _clock(DateTime t) {
    final l = t.toLocal();
    return '${l.hour.toString().padLeft(2, '0')}:${l.minute.toString().padLeft(2, '0')}';
  }
}

class _CourtSheet extends StatefulWidget {
  const _CourtSheet({this.court});
  final Court? court;

  @override
  State<_CourtSheet> createState() => _CourtSheetState();
}

class _CourtSheetState extends State<_CourtSheet> {
  late final _name = TextEditingController(text: widget.court?.name ?? '');
  late final _minutes = TextEditingController(text: widget.court?.slotMinutes?.toString() ?? '');
  late final _price = TextEditingController(
    text: widget.court?.slotPricePaise == null ? '' : (widget.court!.slotPricePaise! / 100).toStringAsFixed(widget.court!.slotPricePaise! % 100 == 0 ? 0 : 2),
  );
  String? _error;

  @override
  void dispose() {
    _name.dispose();
    _minutes.dispose();
    _price.dispose();
    super.dispose();
  }

  void _save() {
    final name = _name.text.trim();
    if (name.isEmpty) return setState(() => _error = 'Enter a court name.');
    final minutesText = _minutes.text.trim();
    final priceText = _price.text.trim();
    final minutes = minutesText.isEmpty ? null : int.tryParse(minutesText);
    if (minutesText.isNotEmpty && (minutes == null || minutes < 5 || minutes > 720)) {
      return setState(() => _error = 'Slot length must be between 5 and 720 minutes.');
    }
    int? paise;
    if (priceText.isNotEmpty) {
      final rupees = double.tryParse(priceText);
      if (rupees == null || rupees < 0) return setState(() => _error = 'Enter a valid price.');
      paise = (rupees * 100).round();
    }
    Navigator.of(context).pop(<String, dynamic>{
      'name': name,
      if (minutes != null) 'slot_minutes': minutes,
      if (paise != null) 'slot_price_paise': paise,
    });
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.fromLTRB(Gap.page, 0, Gap.page, MediaQuery.of(context).viewInsets.bottom + Gap.xxl),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(widget.court == null ? 'Add court' : 'Edit court', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: Gap.md),
          TextField(controller: _name, decoration: const InputDecoration(labelText: 'Court name'), maxLength: 80),
          TextField(
            controller: _minutes,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(labelText: 'Slot length (minutes)', helperText: 'Required for the court to be bookable'),
          ),
          const SizedBox(height: Gap.md),
          TextField(
            controller: _price,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(labelText: 'Price per slot (₹)', helperText: 'Required for the court to be bookable'),
          ),
          if (_error != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text(_error!, style: const TextStyle(color: ZuruvColors.error))),
          const SizedBox(height: Gap.lg),
          SizedBox(width: double.infinity, child: FilledButton(onPressed: _save, child: const Text('Save court'))),
        ],
      ),
    );
  }
}

class _BlockInput {
  const _BlockInput(this.courtId, this.start, this.end, this.reason);
  final String? courtId;
  final DateTime start;
  final DateTime end;
  final String? reason;
}

class _BlockSheet extends StatefulWidget {
  const _BlockSheet({required this.courts});
  final List<Court> courts;

  @override
  State<_BlockSheet> createState() => _BlockSheetState();
}

class _BlockSheetState extends State<_BlockSheet> {
  String? _courtId; // null = whole venue
  DateTime? _date;
  TimeOfDay? _from;
  TimeOfDay? _to;
  final _reason = TextEditingController();
  String? _error;

  @override
  void dispose() {
    _reason.dispose();
    super.dispose();
  }

  Future<void> _pickDate() async {
    final now = DateTime.now();
    final d = await showDatePicker(context: context, initialDate: now, firstDate: now, lastDate: now.add(const Duration(days: 365)));
    if (d != null) setState(() => _date = d);
  }

  Future<void> _pickTime(bool from) async {
    final t = await showTimePicker(context: context, initialTime: const TimeOfDay(hour: 9, minute: 0));
    if (t != null) setState(() => from ? _from = t : _to = t);
  }

  void _save() {
    if (_date == null || _from == null || _to == null) return setState(() => _error = 'Choose a date, start and end time.');
    final start = DateTime(_date!.year, _date!.month, _date!.day, _from!.hour, _from!.minute);
    final end = DateTime(_date!.year, _date!.month, _date!.day, _to!.hour, _to!.minute);
    if (!end.isAfter(start)) return setState(() => _error = 'End time must be after the start time.');
    Navigator.of(context).pop(_BlockInput(_courtId, start, end, _reason.text.trim()));
  }

  String _fmt(TimeOfDay? t) => t == null ? 'Choose' : '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.fromLTRB(Gap.page, 0, Gap.page, MediaQuery.of(context).viewInsets.bottom + Gap.xxl),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Block a time', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: Gap.md),
          DropdownButtonFormField<String?>(
            initialValue: _courtId,
            decoration: const InputDecoration(labelText: 'Applies to'),
            items: [
              const DropdownMenuItem<String?>(value: null, child: Text('Whole venue')),
              for (final c in widget.courts) DropdownMenuItem<String?>(value: c.id, child: Text(c.name)),
            ],
            onChanged: (v) => setState(() => _courtId = v),
          ),
          const SizedBox(height: Gap.md),
          Wrap(spacing: Gap.sm, children: [
            OutlinedButton(onPressed: _pickDate, child: Text(_date == null ? 'Choose date' : formatDate(_date!))),
            OutlinedButton(onPressed: () => _pickTime(true), child: Text('From ${_fmt(_from)}')),
            OutlinedButton(onPressed: () => _pickTime(false), child: Text('To ${_fmt(_to)}')),
          ]),
          const SizedBox(height: Gap.md),
          TextField(controller: _reason, maxLength: 200, decoration: const InputDecoration(labelText: 'Reason (optional)')),
          if (_error != null) Text(_error!, style: const TextStyle(color: ZuruvColors.error)),
          const SizedBox(height: Gap.lg),
          SizedBox(width: double.infinity, child: FilledButton(onPressed: _save, child: const Text('Block time'))),
        ],
      ),
    );
  }
}
