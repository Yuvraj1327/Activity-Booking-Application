import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';

import '../../core/network/api_helpers.dart';
import '../models/catalog.dart';
import '../models/venue.dart';

/// All catalogue/discovery/favorites calls. Uses the single shared Dio client, which attaches
/// the Supabase JWT; the backend decides what the caller may see.
class VenueRepository {
  VenueRepository(this._dio);

  final Dio _dio;

  Future<List<City>> cities() => apiCall(() async {
        final res = await _dio.get<List<dynamic>>('/cities');
        return (res.data ?? const []).map((e) => City.fromJson(e as Map<String, dynamic>)).toList();
      });

  Future<List<VenueCategory>> categories() => apiCall(() async {
        final res = await _dio.get<List<dynamic>>('/categories');
        return (res.data ?? const []).map((e) => VenueCategory.fromJson(e as Map<String, dynamic>)).toList();
      });

  Future<VenuePageData> venues(VenueQuery query, {required int offset, CancelToken? cancelToken}) =>
      apiCall(() async {
        final path = query.favoritesOnly ? '/favorites' : '/venues';
        final params = query.favoritesOnly
            ? {'limit': query.pageSize, 'offset': offset}
            : query.toParams(offset: offset);
        final res = await _dio.get<Map<String, dynamic>>(path, queryParameters: params, cancelToken: cancelToken);
        return VenuePageData.fromJson(res.data ?? const {'items': <dynamic>[]});
      });

  Future<VenueDetail> venue(String id, {double? lat, double? lng}) => apiCall(() async {
        final res = await _dio.get<Map<String, dynamic>>(
          '/venues/$id',
          queryParameters: {if (lat != null && lng != null) ...{'lat': lat, 'lng': lng}},
        );
        return VenueDetail.fromJson(res.data!);
      });

  Future<void> addFavorite(String venueId) =>
      apiCall(() => _dio.post<void>('/favorites', data: {'venue_id': venueId}));

  Future<void> removeFavorite(String venueId) => apiCall(() => _dio.delete<void>('/favorites/$venueId'));
}

final venueRepositoryProvider = Provider<VenueRepository>((ref) => VenueRepository(ref.watch(apiClientProvider)));
