/// Error returned by the ZURUV API: `{code, message, details, request_id}`.
class ApiException implements Exception {
  const ApiException({
    required this.statusCode,
    required this.code,
    required this.message,
    this.details,
    this.requestId,
  });

  final int statusCode;
  final String code;
  final String message;
  final Object? details;
  final String? requestId;

  bool get isNetworkError => statusCode == 0;

  @override
  String toString() => 'ApiException($statusCode, $code, $message)';
}
