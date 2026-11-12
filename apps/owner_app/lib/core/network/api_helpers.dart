import 'package:dio/dio.dart';
import 'package:flutter_shared/flutter_shared.dart';

/// Runs an API call and rethrows any failure as an [ApiException] (never a raw DioException), so
/// every provider and screen handles errors the same way.
Future<T> apiCall<T>(Future<T> Function() call) async {
  try {
    return await call();
  } on ApiException {
    rethrow;
  } on DioException catch (e) {
    throw toApiException(e);
  } catch (e) {
    // Unexpected failures (e.g. a malformed response) surface as a generic, user-safe error.
    throw toApiException(e);
  }
}

/// Message that is safe to show to the user.
String errorMessage(Object error) {
  if (error is ApiException) {
    if (error.isNetworkError) return 'Cannot reach the server. Check your connection.';
    if (error.code == 'SCHEDULE_CONFLICT') return scheduleConflictMessage(error);
    return error.message;
  }
  return 'Something went wrong. Please try again.';
}

/// A change that would break existing bookings is refused by the server (nothing is saved).
/// Lists the affected bookings so the owner knows exactly what is in the way.
String scheduleConflictMessage(ApiException e) {
  final details = e.details;
  if (details is Map) {
    final list = details['bookings'];
    final count = (details['count'] as num?)?.toInt() ?? (list is List ? list.length : 0);
    final codes = <String>[
      if (list is List)
        for (final b in list.take(3))
          if (b is Map && b['booking_code'] != null) b['booking_code'].toString(),
    ];
    final more = count - codes.length;
    return 'This change would affect $count existing booking${count == 1 ? '' : 's'}'
        '${codes.isEmpty ? '' : ' (${codes.join(', ')}${more > 0 ? ' and $more more' : ''})'}. '
        'Nothing was changed. Resolve those bookings first.';
  }
  return e.message;
}
