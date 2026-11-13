import 'dart:math';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';

import 'package:zuruv/customer/shared/models/booking.dart';
import 'package:zuruv/customer/shared/repositories/booking_repository.dart';

/// (venueId, yyyy-MM-dd) -> availability for that date. Always fetched from the server; never
/// computed on the device.
typedef AvailabilityKey = ({String venueId, String date});

final availabilityProvider = FutureProvider.autoDispose.family<Availability, AvailabilityKey>((ref, key) {
  return ref.watch(bookingRepositoryProvider).availability(key.venueId, key.date);
});

/// Bumped whenever a booking is created or cancelled so the My Bookings tabs reload.
final bookingsRevisionProvider = StateProvider<int>((ref) => 0);

final bookingDetailProvider = FutureProvider.autoDispose.family<Booking, String>((ref, id) {
  return ref.watch(bookingRepositoryProvider).get(id);
});

String newIdempotencyKey() {
  final r = Random.secure();
  final bytes = List<int>.generate(16, (_) => r.nextInt(256));
  return bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
}

enum SubmitPhase { idle, submitting, success, conflict, failed, offline }

class BookingSubmit {
  const BookingSubmit({this.phase = SubmitPhase.idle, this.booking, this.message, this.code});

  final SubmitPhase phase;
  final Booking? booking;
  final String? message;
  final String? code;
}

/// Creates one booking. The Idempotency-Key is created once per user intent and reused for
/// retries of the SAME slot, so a double tap or a flaky network can never create two bookings.
class BookingSubmitController extends AutoDisposeNotifier<BookingSubmit> {
  String? _key;
  String? _slotId;

  @override
  BookingSubmit build() => const BookingSubmit();

  Future<void> submit(String resourceId, DateTime startsAt) async {
    if (state.phase == SubmitPhase.submitting) return; // ignore double taps
    final slotId = '$resourceId|${startsAt.toUtc().toIso8601String()}';
    if (_slotId != slotId) {
      _slotId = slotId;
      _key = newIdempotencyKey();
    }
    state = const BookingSubmit(phase: SubmitPhase.submitting);
    try {
      final booking = await ref.read(bookingRepositoryProvider).create(resourceId, startsAt, idempotencyKey: _key!);
      state = BookingSubmit(phase: SubmitPhase.success, booking: booking);
    } on ApiException catch (e) {
      if (e.isNetworkError) {
        // The request may or may not have reached the server: keep the key so a retry is safe.
        state = BookingSubmit(phase: SubmitPhase.offline, message: 'Cannot reach the server. Check your connection and try again.', code: e.code);
      } else if (e.code == 'SLOT_UNAVAILABLE' || e.code == 'SLOT_NOT_BOOKABLE' || e.code == 'INVALID_SLOT') {
        _slotId = null; // a different slot is a new intent
        state = BookingSubmit(phase: SubmitPhase.conflict, message: e.message, code: e.code);
      } else {
        state = BookingSubmit(phase: SubmitPhase.failed, message: e.message, code: e.code);
      }
    } catch (_) {
      state = const BookingSubmit(phase: SubmitPhase.failed, message: 'Something went wrong. Please try again.');
    }
  }

  void reset() => state = const BookingSubmit();
}

final bookingSubmitProvider = NotifierProvider.autoDispose<BookingSubmitController, BookingSubmit>(BookingSubmitController.new);
