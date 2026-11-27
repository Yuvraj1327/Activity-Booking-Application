import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';

import 'package:zuruv/core/network/api_helpers.dart';
import 'package:zuruv/owner/shared/models/models.dart';

/// Every owner call goes through the one shared Dio client (bearer token attached, 401 handled by
/// the auth layer). The backend verifies the Owner role and venue ownership on every request.
class OwnerRepository {
  OwnerRepository(this._dio);

  final Dio _dio;

  // ---- reference data (same endpoints as the customer app)
  Future<List<City>> cities() => apiCall(() async {
        final res = await _dio.get<List<dynamic>>('/cities');
        return [for (final c in res.data!) City.fromJson(c as Map<String, dynamic>)];
      });

  Future<List<Category>> categories() => apiCall(() async {
        final res = await _dio.get<List<dynamic>>('/categories');
        return [for (final c in res.data!) Category.fromJson(c as Map<String, dynamic>)];
      });

  Future<List<Amenity>> amenities() => apiCall(() async {
        final res = await _dio.get<List<dynamic>>('/amenities');
        return [for (final c in res.data!) Amenity.fromJson(c as Map<String, dynamic>)];
      });

  // ---- profile / business
  Future<OwnerBusiness> business() => apiCall(() async {
        final res = await _dio.get<Map<String, dynamic>>('/owners/me');
        return OwnerBusiness.fromJson(res.data!);
      });

  Future<OwnerBusiness> updateBusiness(Map<String, dynamic> changes) => apiCall(() async {
        final res = await _dio.patch<Map<String, dynamic>>('/owners/me', data: changes);
        return OwnerBusiness.fromJson(res.data!);
      });

  Future<UserProfile> updateProfile(Map<String, dynamic> changes) => apiCall(() async {
        final res = await _dio.patch<Map<String, dynamic>>('/profiles/me', data: changes);
        return UserProfile.fromJson(res.data!);
      });

  // ---- venues
  Future<VenuePage> venues({String? query, String? status, int limit = 20, int offset = 0}) => apiCall(() async {
        final res = await _dio.get<Map<String, dynamic>>('/owners/venues', queryParameters: {
          if (query != null && query.isNotEmpty) 'q': query,
          if (status != null) 'status': status,
          'limit': limit,
          'offset': offset,
        });
        return VenuePage.fromJson(res.data!);
      });

  Future<OwnerVenueDetail> venue(String id) => apiCall(() async {
        final res = await _dio.get<Map<String, dynamic>>('/owners/venues/$id');
        return OwnerVenueDetail.fromJson(res.data!);
      });

  Future<OwnerVenueDetail> createVenue(VenueDraft draft) => apiCall(() async {
        final res = await _dio.post<Map<String, dynamic>>('/owners/venues', data: draft.toJson());
        return OwnerVenueDetail.fromJson(res.data!);
      });

  Future<OwnerVenueDetail> updateVenue(String id, VenueDraft draft) => apiCall(() async {
        final res = await _dio.patch<Map<String, dynamic>>('/owners/venues/$id', data: draft.toJson());
        return OwnerVenueDetail.fromJson(res.data!);
      });

  Future<OwnerVenueDetail> publish(String id) => apiCall(() async {
        final res = await _dio.post<Map<String, dynamic>>('/owners/venues/$id/publish');
        return OwnerVenueDetail.fromJson(res.data!);
      });

  Future<OwnerVenueDetail> unpublish(String id) => apiCall(() async {
        final res = await _dio.post<Map<String, dynamic>>('/owners/venues/$id/unpublish');
        return OwnerVenueDetail.fromJson(res.data!);
      });

  Future<void> deleteVenue(String id) => apiCall(() => _dio.delete<void>('/owners/venues/$id'));

  // ---- images (the backend validates type and size, then stores them in Supabase Storage)
  Future<VenueImage> uploadImage(String venueId, {required List<int> bytes, required String filename}) =>
      apiCall(() async {
        final form = FormData.fromMap({
          // The backend identifies the format from the file's bytes, not from this name or type.
          'file': MultipartFile.fromBytes(bytes, filename: filename),
        });
        final res = await _dio.post<Map<String, dynamic>>('/owners/venues/$venueId/images', data: form);
        return VenueImage.fromJson(res.data!);
      });

  Future<void> deleteImage(String venueId, String imageId) =>
      apiCall(() => _dio.delete<void>('/owners/venues/$venueId/images/$imageId'));

  Future<VenueImage> setCover(String venueId, String imageId) => apiCall(() async {
        final res = await _dio.patch<Map<String, dynamic>>('/owners/venues/$venueId/images/$imageId', data: {'is_cover': true});
        return VenueImage.fromJson(res.data!);
      });

  Future<List<VenueImage>> reorderImages(String venueId, List<String> orderedIds) => apiCall(() async {
        final res = await _dio.put<List<dynamic>>('/owners/venues/$venueId/images/order', data: {'image_ids': orderedIds});
        return [for (final i in res.data!) VenueImage.fromJson(i as Map<String, dynamic>)];
      });

  // ---- schedules
  Future<VenueSchedule> schedule(String venueId) => apiCall(() async {
        final res = await _dio.get<Map<String, dynamic>>('/owners/venues/$venueId/schedules');
        return VenueSchedule.fromJson(res.data!);
      });

  Future<VenueSchedule> saveSchedule(String venueId, {List<DayHours>? regular, List<SpecialDate>? special}) => apiCall(() async {
        final res = await _dio.put<Map<String, dynamic>>('/owners/venues/$venueId/schedules', data: {
          if (regular != null) 'regular': [for (final d in regular) d.toJson()],
          if (special != null) 'special': [for (final s in special) s.toJson()],
        });
        return VenueSchedule.fromJson(res.data!);
      });

  // ---- dashboard / analytics
  Future<Dashboard> dashboard() => apiCall(() async {
        final res = await _dio.get<Map<String, dynamic>>('/owners/dashboard');
        return Dashboard.fromJson(res.data!);
      });

  Future<Analytics> analytics({required String from, required String to}) => apiCall(() async {
        final res = await _dio.get<Map<String, dynamic>>('/owners/analytics', queryParameters: {'date_from': from, 'date_to': to});
        return Analytics.fromJson(res.data!);
      });

  // ---- bookings (read-only for owners: they cannot change statuses)
  Future<OwnerBookingPage> bookings(String bucket, {int offset = 0, int limit = 20}) => apiCall(() async {
        final res = await _dio.get<Map<String, dynamic>>('/owners/bookings',
            queryParameters: {'bucket': bucket, 'limit': limit, 'offset': offset});
        return OwnerBookingPage.fromJson(res.data!);
      });

  Future<OwnerBooking> booking(String id) => apiCall(() async {
        final res = await _dio.get<Map<String, dynamic>>('/owners/bookings/$id');
        return OwnerBooking.fromJson(res.data!);
      });

  // ---- courts and blocked periods
  Future<List<Court>> courts(String venueId) => apiCall(() async {
        final res = await _dio.get<List<dynamic>>('/owners/venues/$venueId/resources');
        return [for (final c in res.data!) Court.fromJson(c as Map<String, dynamic>)];
      });

  Future<Court> saveCourt(String venueId, {String? courtId, required Map<String, dynamic> fields}) => apiCall(() async {
        final res = courtId == null
            ? await _dio.post<Map<String, dynamic>>('/owners/venues/$venueId/resources', data: fields)
            : await _dio.patch<Map<String, dynamic>>('/owners/venues/$venueId/resources/$courtId', data: fields);
        return Court.fromJson(res.data!);
      });

  Future<void> deleteCourt(String venueId, String courtId) =>
      apiCall(() => _dio.delete<void>('/owners/venues/$venueId/resources/$courtId'));

  Future<List<TimeBlock>> blocks(String venueId) => apiCall(() async {
        final res = await _dio.get<List<dynamic>>('/owners/venues/$venueId/blocks');
        return [for (final b in res.data!) TimeBlock.fromJson(b as Map<String, dynamic>)];
      });

  Future<TimeBlock> addBlock(String venueId, {String? courtId, required DateTime startsAt, required DateTime endsAt, String? reason}) =>
      apiCall(() async {
        final res = await _dio.post<Map<String, dynamic>>('/owners/venues/$venueId/blocks', data: {
          if (courtId != null) 'resource_id': courtId,
          'starts_at': startsAt.toUtc().toIso8601String(),
          'ends_at': endsAt.toUtc().toIso8601String(),
          if (reason != null && reason.isNotEmpty) 'reason': reason,
        });
        return TimeBlock.fromJson(res.data!);
      });

  Future<void> deleteBlock(String venueId, String blockId) =>
      apiCall(() => _dio.delete<void>('/owners/venues/$venueId/blocks/$blockId'));

  // ---- data that depends on later steps (the API answers honestly that it is not available yet)
  /// Real, confirmed gross payment totals (Step 7). Everything rule-dependent comes back unavailable.
  Future<OwnerEarnings> earnings() => apiCall(() async {
        final res = await _dio.get<Map<String, dynamic>>('/owners/earnings');
        return OwnerEarnings.fromJson(res.data!);
      });

  /// Booking-wise commission and net payable. Read-only; the backend does all the arithmetic.
  Future<EarningsBreakdown> earningsBreakdown() => apiCall(() async {
        final res = await _dio.get<Map<String, dynamic>>('/owners/earnings/breakdown');
        return EarningsBreakdown.fromJson(res.data!);
      });

  Future<OwnerPaymentPage> payments({int offset = 0}) => apiCall(() async {
        final res = await _dio.get<Map<String, dynamic>>('/owners/payments', queryParameters: {'offset': offset});
        return OwnerPaymentPage.fromJson(res.data!);
      });

  Future<OwnerReviewPage> reviews({int? rating, int offset = 0}) => apiCall(() async {
        final res = await _dio.get<Map<String, dynamic>>('/owners/reviews', queryParameters: {
          if (rating != null) 'rating': rating,
          'offset': offset,
        });
        return OwnerReviewPage.fromJson(res.data!);
      });

  /// One reply per review; the server refuses a second one.
  Future<OwnerReview> replyToReview(String reviewId, String body) => apiCall(() async {
        final res = await _dio.post<Map<String, dynamic>>('/owners/reviews/$reviewId/reply', data: {'body': body});
        return OwnerReview.fromJson(res.data!);
      });

  // ---- notifications
  Future<NotificationPage> notifications({String group = 'all', bool unreadOnly = false, int offset = 0}) => apiCall(() async {
        final res = await _dio.get<Map<String, dynamic>>('/owners/notifications', queryParameters: {
          'group': group,
          if (unreadOnly) 'unread_only': true,
          'offset': offset,
        });
        return NotificationPage.fromJson(res.data!);
      });

  Future<void> markRead(String id) => apiCall(() => _dio.post<void>('/owners/notifications/$id/read'));
  Future<void> markAllRead() => apiCall(() => _dio.post<void>('/owners/notifications/read-all'));

  /// Server-side delivery switches (`GET/PUT /notifications/preferences`): push and e-mail.
  Future<NotificationChannels> notificationChannels() => apiCall(() async {
        final res = await _dio.get<Map<String, dynamic>>('/notifications/preferences');
        return NotificationChannels.fromJson(res.data!);
      });

  Future<NotificationChannels> setNotificationChannels({bool? push, bool? email}) => apiCall(() async {
        final res = await _dio.put<Map<String, dynamic>>('/notifications/preferences', data: {
          if (push != null) 'push_enabled': push,
          if (email != null) 'email_enabled': email,
        });
        return NotificationChannels.fromJson(res.data!);
      });

  /// Address suggestions (`GET /places/autocomplete`). The Google key stays on the server; a
  /// 503 `PLACES_NOT_CONFIGURED` surfaces as an [ApiException] the UI explains.
  Future<List<PlaceSuggestion>> searchPlaces(String q, {String? sessionToken}) => apiCall(() async {
        final res = await _dio.get<List<dynamic>>('/places/autocomplete', queryParameters: {
          'q': q,
          if (sessionToken != null) 'session_token': sessionToken,
        });
        return [for (final e in res.data!) PlaceSuggestion.fromJson(e as Map<String, dynamic>)];
      });

  Future<PlaceDetails> placeDetails(String placeId) => apiCall(() async {
        final res = await _dio.get<Map<String, dynamic>>('/places/$placeId');
        return PlaceDetails.fromJson(res.data!);
      });
}

final ownerRepositoryProvider = Provider<OwnerRepository>((ref) => OwnerRepository(ref.watch(apiClientProvider)));

// Reference data for the venue form (same public endpoints the customer side uses).
final citiesProvider = FutureProvider<List<City>>((ref) => ref.watch(ownerRepositoryProvider).cities());
final categoriesProvider = FutureProvider<List<Category>>((ref) => ref.watch(ownerRepositoryProvider).categories());
final amenitiesProvider = FutureProvider<List<Amenity>>((ref) => ref.watch(ownerRepositoryProvider).amenities());

class NotificationChannels {
  const NotificationChannels({required this.push, required this.email});

  factory NotificationChannels.fromJson(Map<String, dynamic> j) =>
      NotificationChannels(push: j['push_enabled'] as bool, email: j['email_enabled'] as bool);

  final bool push;
  final bool email;
}
