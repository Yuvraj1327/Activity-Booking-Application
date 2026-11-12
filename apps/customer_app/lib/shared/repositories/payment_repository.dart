import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';

import '../../core/network/api_helpers.dart';
import '../models/payment.dart';

/// Payment calls. The amount is never sent: the backend computes it from the booking.
class PaymentRepository {
  PaymentRepository(this._dio);

  final Dio _dio;

  Future<CreateOrderResult> createOrder(String bookingId) => apiCall(() async {
        final res = await _dio.post<Map<String, dynamic>>('/payments/create-order', data: {'booking_id': bookingId});
        return CreateOrderResult.fromJson(res.data!);
      });

  /// Sends the checkout result to the backend, which checks the signature and asks Razorpay.
  Future<PaymentInfo> verify({required String orderId, required String paymentId, required String signature}) =>
      apiCall(() async {
        final res = await _dio.post<Map<String, dynamic>>('/payments/verify', data: {
          'razorpay_order_id': orderId,
          'razorpay_payment_id': paymentId,
          'razorpay_signature': signature,
        });
        return PaymentInfo.fromJson(res.data!);
      });

  Future<PaymentInfo> get(String paymentId) => apiCall(() async {
        final res = await _dio.get<Map<String, dynamic>>('/payments/$paymentId');
        return PaymentInfo.fromJson(res.data!);
      });

  Future<PaymentPageData> history({required int offset, int limit = 20}) => apiCall(() async {
        final res = await _dio.get<Map<String, dynamic>>(
          '/payments/history',
          queryParameters: {'limit': limit, 'offset': offset},
        );
        return PaymentPageData.fromJson(res.data!);
      });
}

final paymentRepositoryProvider = Provider<PaymentRepository>((ref) => PaymentRepository(ref.watch(apiClientProvider)));
