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
    return error.isNetworkError ? 'Cannot reach the server. Check your connection.' : error.message;
  }
  return 'Something went wrong. Please try again.';
}
