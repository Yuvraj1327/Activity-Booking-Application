import 'package:flutter_shared/flutter_shared.dart';
import 'package:zuruv/core/settings/settings_repository.dart';

/// In-memory stand-in for the Settings API that records what the app sent.
class FakeSettingsRepository implements SettingsRepository {
  FakeSettingsRepository({this.failNext = false});

  NotificationPrefs prefs = const NotificationPrefs();
  List<String> interestIds = [];
  final List<Map<String, bool>> prefUpdates = [];
  final List<String> languages = [];
  final List<Map<String, String>> sent = [];
  final List<SupportTicket> ticketList = [];
  int deletionRequests = 0;
  int deletionCancels = 0;
  bool failNext;
  UserProfile? profile;

  /// Published admin content, keyed by slug (the real API only returns published entries).
  final Map<String, Map<String, dynamic>> contentBySlug = {};
  final List<Map<String, dynamic>> contentFaqs = [];

  @override
  Future<Map<String, dynamic>?> contentPage(String slug) async => contentBySlug[slug];

  @override
  Future<List<Map<String, dynamic>>> contentList({required String kind, required String audience}) async => contentFaqs;

  void _maybeFail() {
    if (failNext) {
      failNext = false;
      throw const ApiException(statusCode: 500, code: 'BOOM', message: 'Server said no.');
    }
  }

  UserProfile _p({String? language, DateTime? deletion}) {
    final b = profile!;
    return UserProfile(
      id: b.id,
      role: b.role,
      status: b.status,
      fullName: b.fullName,
      email: b.email,
      phone: b.phone,
      language: language ?? b.language,
      deletionRequestedAt: deletion,
    );
  }

  @override
  Future<NotificationPrefs> notificationPrefs() async => prefs;

  @override
  Future<NotificationPrefs> setNotificationPrefs(Map<String, bool> changes) async {
    _maybeFail();
    prefUpdates.add(changes);
    prefs = NotificationPrefs(
      push: changes['push_enabled'] ?? prefs.push,
      email: changes['email_enabled'] ?? prefs.email,
      booking: changes['booking_enabled'] ?? prefs.booking,
      payment: changes['payment_enabled'] ?? prefs.payment,
      promo: changes['promo_enabled'] ?? prefs.promo,
    );
    return prefs;
  }

  @override
  Future<UserProfile> setLanguage(String code) async {
    _maybeFail();
    languages.add(code);
    profile = _p(language: code);
    return profile!;
  }

  @override
  Future<List<String>> interests() async => interestIds;

  @override
  Future<List<String>> setInterests(List<String> categoryIds) async {
    _maybeFail();
    interestIds = categoryIds;
    return interestIds;
  }

  @override
  Future<UserProfile> requestDeletion() async {
    _maybeFail();
    deletionRequests++;
    return _p(deletion: DateTime(2026, 11, 20));
  }

  @override
  Future<UserProfile> cancelDeletion() async {
    deletionCancels++;
    return _p();
  }

  @override
  Future<SupportTicket> sendTicket({
    required String kind,
    required String subject,
    required String message,
    String? appVersion,
    String? platform,
  }) async {
    _maybeFail();
    sent.add({'kind': kind, 'subject': subject, 'message': message});
    final t = SupportTicket(id: 't${sent.length}', kind: kind, subject: subject, status: 'open', createdAt: DateTime(2026, 11, 20));
    ticketList.insert(0, t);
    return t;
  }

  @override
  Future<List<SupportTicket>> tickets() async => ticketList;
}
