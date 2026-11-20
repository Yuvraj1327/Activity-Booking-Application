import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';

import 'package:zuruv/core/network/api_helpers.dart';

/// Notification switches stored on the account (`/notifications/preferences`).
class NotificationPrefs {
  const NotificationPrefs({
    this.push = true,
    this.email = true,
    this.booking = true,
    this.payment = true,
    this.promo = true,
  });

  factory NotificationPrefs.fromJson(Map<String, dynamic> j) => NotificationPrefs(
        push: j['push_enabled'] as bool? ?? true,
        email: j['email_enabled'] as bool? ?? true,
        booking: j['booking_enabled'] as bool? ?? true,
        payment: j['payment_enabled'] as bool? ?? true,
        promo: j['promo_enabled'] as bool? ?? true,
      );

  final bool push;
  final bool email;
  final bool booking;
  final bool payment;
  final bool promo;
}

class SupportTicket {
  const SupportTicket({required this.id, required this.kind, required this.subject, required this.status, required this.createdAt});

  factory SupportTicket.fromJson(Map<String, dynamic> j) => SupportTicket(
        id: j['id'] as String,
        kind: j['kind'] as String,
        subject: j['subject'] as String,
        status: j['status'] as String,
        createdAt: DateTime.tryParse(j['created_at'] as String? ?? '')?.toLocal() ?? DateTime.now(),
      );

  final String id;
  final String kind;
  final String subject;
  final String status;
  final DateTime createdAt;
}

/// Everything the Settings screens read and write, for both roles. Each call is made with the
/// signed-in user's token, and the API only ever touches that user's own rows.
class SettingsRepository {
  SettingsRepository(this._dio);

  final Dio _dio;

  Future<NotificationPrefs> notificationPrefs() => apiCall(() async {
        final res = await _dio.get<Map<String, dynamic>>('/notifications/preferences');
        return NotificationPrefs.fromJson(res.data!);
      });

  /// Sends only the switches that changed.
  Future<NotificationPrefs> setNotificationPrefs(Map<String, bool> changes) => apiCall(() async {
        final res = await _dio.put<Map<String, dynamic>>('/notifications/preferences', data: changes);
        return NotificationPrefs.fromJson(res.data!);
      });

  Future<UserProfile> setLanguage(String code) => apiCall(() async {
        final res = await _dio.patch<Map<String, dynamic>>('/profiles/me', data: {'language': code});
        return UserProfile.fromJson(res.data!);
      });

  Future<List<String>> interests() => apiCall(() async {
        final res = await _dio.get<Map<String, dynamic>>('/customers/me');
        return [for (final id in (res.data!['preferred_category_ids'] as List? ?? const [])) id as String];
      });

  Future<List<String>> setInterests(List<String> categoryIds) => apiCall(() async {
        final res = await _dio.patch<Map<String, dynamic>>('/customers/me', data: {'preferred_category_ids': categoryIds});
        return [for (final id in (res.data!['preferred_category_ids'] as List? ?? const [])) id as String];
      });

  Future<UserProfile> requestDeletion() => apiCall(() async {
        final res = await _dio.post<Map<String, dynamic>>('/profiles/me/deletion-request');
        return UserProfile.fromJson(res.data!);
      });

  Future<UserProfile> cancelDeletion() => apiCall(() async {
        final res = await _dio.delete<Map<String, dynamic>>('/profiles/me/deletion-request');
        return UserProfile.fromJson(res.data!);
      });

  Future<SupportTicket> sendTicket({
    required String kind,
    required String subject,
    required String message,
    String? appVersion,
    String? platform,
  }) =>
      apiCall(() async {
        final res = await _dio.post<Map<String, dynamic>>('/support/tickets', data: {
          'kind': kind,
          'subject': subject,
          'message': message,
          if (appVersion != null) 'app_version': appVersion,
          if (platform != null) 'platform': platform,
        });
        return SupportTicket.fromJson(res.data!);
      });

  Future<List<SupportTicket>> tickets() => apiCall(() async {
        final res = await _dio.get<List<dynamic>>('/support/tickets');
        return [for (final t in res.data!) SupportTicket.fromJson(t as Map<String, dynamic>)];
      });
}

final settingsRepositoryProvider = Provider<SettingsRepository>((ref) => SettingsRepository(ref.watch(apiClientProvider)));
