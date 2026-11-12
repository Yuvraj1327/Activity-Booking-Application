import 'package:dio/dio.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../config/app_env.dart';
import 'api_exception.dart';

/// Dio client for the ZURUV API. Attaches the Supabase access token when a session
/// exists and converts failures into [ApiException].
Dio createApiClient({String? baseUrl, String? Function()? accessToken}) {
  final dio = Dio(
    BaseOptions(
      baseUrl: baseUrl ?? AppEnv.apiBaseUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 20),
      headers: {'Accept': 'application/json'},
    ),
  );

  dio.interceptors.add(
    InterceptorsWrapper(
      onRequest: (options, handler) {
        final token = (accessToken ?? _supabaseToken)();
        if (token != null) options.headers['Authorization'] = 'Bearer $token';
        handler.next(options);
      },
      onError: (e, handler) {
        handler.next(e.copyWith(error: _toApiException(e)));
      },
    ),
  );
  return dio;
}

String? _supabaseToken() {
  try {
    return Supabase.instance.client.auth.currentSession?.accessToken;
  } catch (_) {
    return null; // Supabase not initialised (not configured).
  }
}

/// Extracts the [ApiException] from any error thrown by the client above.
ApiException toApiException(Object error) {
  if (error is DioException) return _toApiException(error);
  return const ApiException(statusCode: 0, code: 'UNKNOWN', message: 'Something went wrong.');
}

ApiException _toApiException(DioException e) {
  final existing = e.error;
  if (existing is ApiException) return existing;

  final response = e.response;
  final data = response?.data;
  if (response != null && data is Map<String, dynamic>) {
    return ApiException(
      statusCode: response.statusCode ?? 0,
      code: (data['code'] as String?) ?? 'HTTP_${response.statusCode}',
      message: (data['message'] as String?) ?? 'Request failed.',
      details: data['details'],
      requestId: data['request_id'] as String?,
    );
  }
  if (response != null) {
    return ApiException(
      statusCode: response.statusCode ?? 0,
      code: 'HTTP_${response.statusCode}',
      message: 'Request failed.',
    );
  }
  return const ApiException(
    statusCode: 0,
    code: 'NETWORK_ERROR',
    message: 'Cannot reach the server. Check your connection.',
  );
}
