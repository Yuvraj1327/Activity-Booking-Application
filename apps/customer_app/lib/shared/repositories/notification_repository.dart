import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';

import '../../core/network/api_helpers.dart';
import '../models/app_notification.dart';

class NotificationRepository {
  NotificationRepository(this._dio);

  final Dio _dio;

  Future<NotificationPageData> list({int limit = 50}) => apiCall(() async {
        final res = await _dio.get<Map<String, dynamic>>('/notifications', queryParameters: {'limit': limit});
        return NotificationPageData.fromJson(res.data!);
      });

  Future<int> unreadCount() => apiCall(() async {
        final res = await _dio.get<Map<String, dynamic>>('/notifications/unread-count');
        return (res.data!['unread_count'] as num).toInt();
      });

  Future<void> markRead(String id) => apiCall(() async {
        await _dio.post<void>('/notifications/$id/read');
      });

  Future<void> markAllRead() => apiCall(() async {
        await _dio.post<void>('/notifications/read-all');
      });
}

final notificationRepositoryProvider =
    Provider<NotificationRepository>((ref) => NotificationRepository(ref.watch(apiClientProvider)));
