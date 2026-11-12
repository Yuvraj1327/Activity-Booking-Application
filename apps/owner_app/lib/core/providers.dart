import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';

/// Result of GET /health, for the foundation status card.
final backendHealthProvider = FutureProvider.autoDispose<Map<String, dynamic>>((ref) async {
  final dio = ref.watch(apiClientProvider);
  try {
    final res = await dio.getUri<Map<String, dynamic>>(AppEnv.healthUri);
    return res.data ?? <String, dynamic>{};
  } catch (e) {
    throw toApiException(e);
  }
});
