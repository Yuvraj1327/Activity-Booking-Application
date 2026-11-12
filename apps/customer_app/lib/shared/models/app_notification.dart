class AppNotification {
  const AppNotification({
    required this.id,
    required this.type,
    required this.title,
    required this.isRead,
    required this.createdAt,
    this.body,
    this.bookingId,
    this.paymentId,
  });

  final String id;
  final String type;
  final String title;
  final String? body;
  final bool isRead;
  final DateTime createdAt;
  final String? bookingId;
  final String? paymentId;

  factory AppNotification.fromJson(Map<String, dynamic> j) => AppNotification(
        id: j['id'] as String,
        type: (j['type'] as String?) ?? '',
        title: (j['title'] as String?) ?? '',
        body: j['body'] as String?,
        isRead: (j['is_read'] as bool?) ?? false,
        createdAt: DateTime.parse(j['created_at'] as String),
        bookingId: j['booking_id'] as String?,
        paymentId: j['payment_id'] as String?,
      );
}

class NotificationPageData {
  const NotificationPageData({required this.items, required this.unreadCount});

  final List<AppNotification> items;
  final int unreadCount;

  factory NotificationPageData.fromJson(Map<String, dynamic> j) => NotificationPageData(
        items: ((j['items'] as List<dynamic>?) ?? const [])
            .map((e) => AppNotification.fromJson(e as Map<String, dynamic>))
            .toList(),
        unreadCount: (j['unread_count'] as num?)?.toInt() ?? 0,
      );
}
