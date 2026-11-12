import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:go_router/go_router.dart';

import '../../core/constants/tokens.dart';
import '../../core/network/api_helpers.dart';
import '../../core/utils/dates.dart';
import '../../core/utils/format.dart';
import '../../shared/models/booking.dart';
import '../../shared/repositories/booking_repository.dart';
import '../../shared/widgets/common_widgets.dart';
import '../venue_details/venue_detail_provider.dart';
import 'booking_providers.dart';

/// Choose a date, a court and a slot, then review and book.
/// Every slot shown comes from the server; this screen never works out availability itself.
class BookingScreen extends ConsumerStatefulWidget {
  const BookingScreen({super.key, required this.venueId, this.today});

  final String venueId;

  /// Overridable for tests.
  final DateTime? today;

  @override
  ConsumerState<BookingScreen> createState() => _BookingScreenState();
}

class _BookingScreenState extends ConsumerState<BookingScreen> {
  static const _daysShown = 14;
  late final List<DateTime> _days = nextDays(widget.today ?? DateTime.now(), _daysShown);
  late DateTime _date = _days.first;
  CourtAvailability? _court;
  Slot? _slot;

  AvailabilityKey get _key => (venueId: widget.venueId, date: apiDate(_date));

  void _pickDate(DateTime d) => setState(() {
        _date = d;
        _court = null;
        _slot = null;
      });

  Future<void> _review() async {
    final court = _court;
    final slot = _slot;
    if (court == null || slot == null) return;
    final venueName = ref.read(venueDetailProvider(widget.venueId)).valueOrNull?.name ?? 'this venue';
    final outcome = await showModalBottomSheet<_ReviewOutcome>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => _ReviewSheet(venueName: venueName, court: court, slot: slot, date: apiDate(_date)),
    );
    if (!mounted) return;
    switch (outcome) {
      case _ReviewOutcome.booked:
        final booking = ref.read(bookingSubmitProvider).booking;
        ref.read(bookingsRevisionProvider.notifier).state++;
        ref.invalidate(availabilityProvider(_key));
        ref.read(bookingSubmitProvider.notifier).reset();
        if (booking != null) {
          // A held booking goes straight to payment; an already-confirmed one (instant mode) to details.
          context.pushReplacement(booking.isHold ? '/bookings/${booking.id}/pay' : '/bookings/${booking.id}');
        }
      case _ReviewOutcome.slotTaken:
        // Someone else got there first (or the schedule changed): reload the real availability.
        setState(() => _slot = null);
        ref.invalidate(availabilityProvider(_key));
        ref.read(bookingSubmitProvider.notifier).reset();
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('That slot is no longer available. Please pick another.')),
        );
      case _ReviewOutcome.dismissed || null:
        break;
    }
  }

  @override
  Widget build(BuildContext context) {
    final availability = ref.watch(availabilityProvider(_key));
    // Keeps the submit state alive while the review sheet is closing (it is auto-disposed).
    ref.listen<BookingSubmit>(bookingSubmitProvider, (_, __) {});
    final venueName = ref.watch(venueDetailProvider(widget.venueId)).valueOrNull?.name;
    return Scaffold(
      appBar: AppBar(title: Text(venueName ?? 'Book a slot')),
      body: Column(
        children: [
          _DateStrip(days: _days, selected: _date, onSelect: _pickDate),
          const Divider(height: 1),
          Expanded(
            child: availability.when(
              loading: () => const LoadingView(),
              error: (e, _) => ErrorView(message: errorMessage(e), onRetry: () => ref.invalidate(availabilityProvider(_key))),
              data: (a) => RefreshIndicator(
                onRefresh: () async => ref.refresh(availabilityProvider(_key).future),
                child: _Courts(
                  availability: a,
                  selectedCourt: _court,
                  selectedSlot: _slot,
                  onSelect: (court, slot) => setState(() {
                    _court = court;
                    _slot = slot;
                  }),
                ),
              ),
            ),
          ),
        ],
      ),
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(Gap.page, Gap.sm, Gap.page, Gap.md),
          child: Row(
            children: [
              Expanded(
                child: _slot == null
                    ? Text('Select a slot', style: Theme.of(context).textTheme.bodyMedium)
                    : Column(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('${_court!.name} · ${_slot!.localStart}–${_slot!.localEnd}', style: Theme.of(context).textTheme.titleSmall),
                          Text(formatMoney(_slot!.pricePaise, currency: _court!.currency), style: Theme.of(context).textTheme.bodySmall),
                        ],
                      ),
              ),
              const SizedBox(width: Gap.md),
              FilledButton(
                onPressed: _slot == null ? null : _review,
                child: const Text('Review & book'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _DateStrip extends StatelessWidget {
  const _DateStrip({required this.days, required this.selected, required this.onSelect});

  final List<DateTime> days;
  final DateTime selected;
  final ValueChanged<DateTime> onSelect;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SizedBox(
      height: 84,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: Gap.page, vertical: Gap.md),
        itemCount: days.length,
        separatorBuilder: (_, __) => const SizedBox(width: Gap.sm),
        itemBuilder: (_, i) {
          final d = days[i];
          final isSelected = d == selected;
          return Semantics(
            button: true,
            selected: isSelected,
            label: '${weekdayShort(d)} ${d.day} ${monthShort(d)}',
            child: InkWell(
              borderRadius: BorderRadius.circular(Radii.button),
              onTap: () => onSelect(d),
              child: Container(
                width: 56,
                decoration: BoxDecoration(
                  color: isSelected ? theme.colorScheme.primary : theme.colorScheme.surface,
                  borderRadius: BorderRadius.circular(Radii.button),
                  border: Border.all(color: isSelected ? theme.colorScheme.primary : theme.dividerColor),
                ),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(weekdayShort(d), style: theme.textTheme.bodySmall?.copyWith(color: isSelected ? theme.colorScheme.onPrimary : null)),
                    Text('${d.day}', style: theme.textTheme.titleMedium?.copyWith(color: isSelected ? theme.colorScheme.onPrimary : null)),
                    Text(monthShort(d), style: theme.textTheme.bodySmall?.copyWith(color: isSelected ? theme.colorScheme.onPrimary : null)),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}

class _Courts extends StatelessWidget {
  const _Courts({required this.availability, required this.selectedCourt, required this.selectedSlot, required this.onSelect});

  final Availability availability;
  final CourtAvailability? selectedCourt;
  final Slot? selectedSlot;
  final void Function(CourtAvailability court, Slot slot) onSelect;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    if (availability.courts.isEmpty) {
      return ListView(children: const [
        SizedBox(height: 80),
        EmptyState(icon: Icons.sports_tennis_outlined, title: 'Not open for booking yet', message: 'This venue has not added any courts.'),
      ]);
    }
    final closedMessage = availability.closedReason == null
        ? null
        : availability.note ?? (availability.closedReason == 'special_closure' ? 'Closed on this date.' : 'Closed on this day.');
    return ListView(
      padding: const EdgeInsets.all(Gap.page),
      children: [
        if (closedMessage != null)
          Padding(
            padding: const EdgeInsets.only(bottom: Gap.lg),
            child: Row(children: [
              Icon(Icons.event_busy_outlined, color: theme.colorScheme.error),
              const SizedBox(width: Gap.sm),
              Expanded(child: Text(closedMessage, style: theme.textTheme.titleSmall)),
            ]),
          ),
        for (final court in availability.courts) ...[
          Row(children: [
            Expanded(child: Text(court.name, style: theme.textTheme.titleMedium)),
            if (court.slotMinutes != null && court.slotPricePaise != null)
              Text('${formatMoney(court.slotPricePaise!, currency: court.currency)} · ${prettyDuration(court.slotMinutes!)}', style: theme.textTheme.bodySmall),
          ]),
          const SizedBox(height: Gap.sm),
          if (court.slots.isEmpty)
            Text(court.message ?? 'No slots available.', style: theme.textTheme.bodySmall)
          else
            Wrap(
              spacing: Gap.sm,
              runSpacing: Gap.sm,
              children: [
                for (final slot in court.slots)
                  ChoiceChip(
                    label: Text(slot.localStart),
                    selected: selectedCourt?.resourceId == court.resourceId && selectedSlot == slot,
                    onSelected: (_) => onSelect(court, slot),
                  ),
              ],
            ),
          const SizedBox(height: Gap.xxl),
        ],
      ],
    );
  }
}

enum _ReviewOutcome { booked, slotTaken, dismissed }

/// Re-checks the slot with the server (quote) before showing the price, then creates the booking.
class _ReviewSheet extends ConsumerStatefulWidget {
  const _ReviewSheet({required this.venueName, required this.court, required this.slot, required this.date});

  final String venueName;
  final CourtAvailability court;
  final Slot slot;
  final String date;

  @override
  ConsumerState<_ReviewSheet> createState() => _ReviewSheetState();
}

class _ReviewSheetState extends ConsumerState<_ReviewSheet> {
  late Future<Quote> _quote = _load();

  Future<Quote> _load() => ref.read(bookingRepositoryProvider).quote(widget.court.resourceId, widget.slot.startsAt);

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final submit = ref.watch(bookingSubmitProvider);
    ref.listen<BookingSubmit>(bookingSubmitProvider, (_, next) {
      if (next.phase == SubmitPhase.success) Navigator.of(context).pop(_ReviewOutcome.booked);
      if (next.phase == SubmitPhase.conflict) Navigator.of(context).pop(_ReviewOutcome.slotTaken);
    });
    final busy = submit.phase == SubmitPhase.submitting;
    return Padding(
      padding: EdgeInsets.fromLTRB(Gap.page, 0, Gap.page, MediaQuery.of(context).viewInsets.bottom + Gap.xxl),
      child: FutureBuilder<Quote>(
        future: _quote,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const SizedBox(height: 160, child: LoadingView());
          }
          final err = snap.error;
          if (err != null) {
            final taken = err is ApiException && (err.code == 'SLOT_UNAVAILABLE' || err.code == 'SLOT_NOT_BOOKABLE' || err.code == 'INVALID_SLOT');
            if (taken) {
              WidgetsBinding.instance.addPostFrameCallback((_) {
                if (mounted) Navigator.of(context).pop(_ReviewOutcome.slotTaken);
              });
              return const SizedBox(height: 160, child: LoadingView());
            }
            return Column(mainAxisSize: MainAxisSize.min, children: [
              ErrorView(message: errorMessage(err), onRetry: () => setState(() => _quote = _load())),
            ]);
          }
          final q = snap.data!;
          return Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Review your booking', style: theme.textTheme.titleLarge),
              const SizedBox(height: Gap.md),
              _Row('Venue', widget.venueName),
              _Row('Court', widget.court.name),
              _Row('Date', prettyDate(widget.date)),
              _Row('Time', '${widget.slot.localStart} – ${widget.slot.localEnd} (${prettyDuration(q.durationMinutes)})'),
              const Divider(height: Gap.xxl),
              _Row('Slot price', formatMoney(q.baseAmountPaise, currency: q.currency)),
              if (q.feesPaise > 0) _Row('Fees', formatMoney(q.feesPaise, currency: q.currency)),
              if (q.taxPaise > 0) _Row('Tax', formatMoney(q.taxPaise, currency: q.currency)),
              if (q.discountPaise > 0) _Row('Discount', '-${formatMoney(q.discountPaise, currency: q.currency)}'),
              _Row('Total', formatMoney(q.totalAmountPaise, currency: q.currency), bold: true),
              const SizedBox(height: Gap.sm),
              Text(
                'Your slot is held for a short time while you pay. The booking is confirmed only after '
                'your payment is verified.',
                style: theme.textTheme.bodySmall,
              ),
              if (submit.phase == SubmitPhase.failed || submit.phase == SubmitPhase.offline) ...[
                const SizedBox(height: Gap.md),
                Text(submit.message ?? 'Could not book. Please try again.', style: theme.textTheme.bodyMedium?.copyWith(color: theme.colorScheme.error)),
              ],
              const SizedBox(height: Gap.lg),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: busy ? null : () => ref.read(bookingSubmitProvider.notifier).submit(widget.court.resourceId, widget.slot.startsAt),
                  child: busy
                      ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                      : Text(submit.phase == SubmitPhase.failed || submit.phase == SubmitPhase.offline ? 'Try again' : 'Continue to payment'),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _Row extends StatelessWidget {
  const _Row(this.label, this.value, {this.bold = false});

  final String label;
  final String value;
  final bool bold;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final style = bold ? theme.textTheme.titleMedium : theme.textTheme.bodyMedium;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: theme.textTheme.bodySmall),
          const SizedBox(width: Gap.lg),
          Flexible(child: Text(value, style: style, textAlign: TextAlign.end)),
        ],
      ),
    );
  }
}
