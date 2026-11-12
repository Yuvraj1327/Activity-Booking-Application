import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';

import '../../core/network/api_helpers.dart';

class CustomerSettings {
  const CustomerSettings({required this.profile, this.preferredCityId});
  final UserProfile profile;
  final String? preferredCityId;
}

/// `GET/PATCH /profiles/me` (base profile) and `GET/PATCH /customers/me` (preferred city).
class ProfileRepository {
  ProfileRepository(this._dio);

  final Dio _dio;

  Future<CustomerSettings> me() => apiCall(() async {
        final res = await _dio.get<Map<String, dynamic>>('/customers/me');
        final data = res.data!;
        return CustomerSettings(
          profile: UserProfile.fromJson(data['profile'] as Map<String, dynamic>),
          preferredCityId: data['preferred_city_id'] as String?,
        );
      });

  /// PATCH /profiles/me with only the given fields. A key with a null value clears that field
  /// (allowed for `phone`); `full_name` can never be null.
  Future<UserProfile> updateProfile(Map<String, dynamic> changes) => apiCall(() async {
        final res = await _dio.patch<Map<String, dynamic>>('/profiles/me', data: changes);
        return UserProfile.fromJson(res.data!);
      });

  Future<void> setPreferredCity(String cityId) =>
      apiCall(() => _dio.patch<void>('/customers/me', data: {'preferred_city_id': cityId}));
}

final profileRepositoryProvider = Provider<ProfileRepository>((ref) => ProfileRepository(ref.watch(apiClientProvider)));
