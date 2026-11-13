import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';

import 'package:zuruv/core/network/api_helpers.dart';
import 'package:zuruv/customer/shared/models/booking.dart';

/// Availability and booking calls. Availability, price and status are decided by the backend;
/// this class only transports them.
class BookingRepository {
  BookingRepository(this._dio);

  final Dio _dio;

  Future<Availability> availability(String venueId, String date, {String? resourceId}) => apiCall(() async {
        final res = await _dio.get<Map<String, dynamic>>(
          '/venues/$venueId/availability',
          queryParameters: {'date': date, if (resourceId != null) 'resource_id': resourceId},
        );
        return Availability.fromJson(res.data!);
      });

  Future<Quote> quote(String resourceId, DateTime startsAt) => apiCall(() async {
        final res = await _dio.post<Map<String, dynamic>>(
          '/bookings/quote',
          data: {'resource_id': resourceId, 'starts_at': startsAt.toUtc().toIso8601String()},
        );
        return Quote.fromJson(res.data!);
      });

  /// [idempotencyKey] makes a retry of the same tap safe: the server returns the first booking.
  Future<Booking> create(String resourceId, DateTime startsAt, {required String idempotencyKey}) =>
      apiCall(() async {
        final res = await _dio.post<Map<String, dynamic>>(
          '/bookings',
          data: {'resource_id': resourceId, 'starts_at': startsAt.toUtc().toIso8601String()},
          options: Options(headers: {'Idempotency-Key': idempotencyKey}),
        );
        return Booking.fromJson(res.data!);
      });

  Future<BookingPageData> list(String bucket, {required int offset, int limit = 20}) => apiCall(() async {
        final res = await _dio.get<Map<String, dynamic>>(
          '/bookings',
          queryParameters: {'bucket': bucket, 'limit': limit, 'offset': offset},
        );
        return BookingPageData.fromJson(res.data!);
      });

  Future<Booking> get(String id) => apiCall(() async {
        final res = await _dio.get<Map<String, dynamic>>('/bookings/$id');
        return Booking.fromJson(res.data!);
      });

  Future<CancellationPreview> cancellationPreview(String id) => apiCall(() async {
        final res = await _dio.get<Map<String, dynamic>>('/bookings/$id/cancellation-preview');
        return CancellationPreview.fromJson(res.data!);
      });

  Future<Booking> cancel(String id, {String? reason}) => apiCall(() async {
        final res = await _dio.post<Map<String, dynamic>>(
          '/bookings/$id/cancel',
          data: {if (reason != null && reason.trim().isNotEmpty) 'reason': reason.trim()},
        );
        return Booking.fromJson(res.data!);
      });
}

final bookingRepositoryProvider = Provider<BookingRepository>((ref) => BookingRepository(ref.watch(apiClientProvider)));
