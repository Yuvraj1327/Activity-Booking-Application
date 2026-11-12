import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('unconfigured environment is reported as not configured', () {
    expect(AppEnv.supabaseConfigured, isFalse);
  });

  test('health URI is at the server root', () {
    expect(AppEnv.healthUri.path, '/health');
  });

  test('DioException with API body maps to ApiException', () {
    final req = RequestOptions(path: '/x');
    final e = DioException(
      requestOptions: req,
      response: Response(
        requestOptions: req,
        statusCode: 409,
        data: {'code': 'SLOT_UNAVAILABLE', 'message': 'Taken.', 'details': null, 'request_id': 'r1'},
      ),
    );
    final api = toApiException(e);
    expect(api.code, 'SLOT_UNAVAILABLE');
    expect(api.requestId, 'r1');
  });

  test('connection failure maps to network error', () {
    final e = DioException(requestOptions: RequestOptions(path: '/x'), type: DioExceptionType.connectionError);
    expect(toApiException(e).isNetworkError, isTrue);
  });

  testWidgets('theme builds and ErrorView renders retry', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildZuruvTheme(primary: ZuruvColors.customerPrimary),
        home: Scaffold(body: ErrorView(message: 'Oops', onRetry: () {})),
      ),
    );
    expect(find.text('Oops'), findsOneWidget);
    expect(find.text('Try again'), findsOneWidget);
  });
}
