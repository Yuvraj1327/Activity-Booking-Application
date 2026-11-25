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
      onRequest: (options, handler) async {
        // Only the real Supabase session can be refreshed; an injected token provider is used as is.
        if (accessToken == null) await _refreshIfExpiring();
        final token = (accessToken ?? _supabaseToken)();
        if (token != null) options.headers['Authorization'] = 'Bearer $token';
        handler.next(options);
      },
      onError: (e, handler) async {
        // A 401 usually means the access token expired while the app was in the background
        // (the SDK's refresh timer does not run then). Refresh once and retry before giving up,
        // otherwise the user would be signed out for no reason.
        final req = e.requestOptions;
        if (accessToken == null && e.response?.statusCode == 401 && req.extra['_retried'] != true) {
          final fresh = await _forceRefresh();
          if (fresh != null) {
            try {
              req.extra['_retried'] = true;
              req.headers['Authorization'] = 'Bearer $fresh';
              final res = await dio.fetch<dynamic>(req);
              return handler.resolve(res);
            } on DioException catch (retryError) {
              return handler.next(retryError.copyWith(error: _toApiException(retryError)));
            }
          }
        }
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

/// Refreshes the session when the access token is expired or about to expire.
Future<void> _refreshIfExpiring() async {
  try {
    final auth = Supabase.instance.client.auth;
    final session = auth.currentSession;
    if (session == null) return;
    final exp = session.expiresAt; // seconds since epoch
    if (exp == null) return;
    final now = DateTime.now().millisecondsSinceEpoch ~/ 1000;
    if (exp - now > 60) return;
    await auth.refreshSession();
  } catch (_) {
    // Offline or refresh failed: send the request anyway; a 401 is handled by the retry below.
  }
}

/// Forces a refresh and returns the new access token, or null when it was not possible.
Future<String?> _forceRefresh() async {
  try {
    final res = await Supabase.instance.client.auth.refreshSession();
    return res.session?.accessToken;
  } catch (_) {
    return null;
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
