import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:flutter_test/flutter_test.dart';

class _Adapter implements HttpClientAdapter {
  final requests = <RequestOptions>[];
  bool fail = false;

  @override
  Future<ResponseBody> fetch(RequestOptions options, Stream<Uint8List>? requestStream, Future<void>? cancelFuture) async {
    requests.add(options);
    if (fail) throw DioException(requestOptions: options, type: DioExceptionType.connectionError);
    return ResponseBody.fromString('', 204);
  }

  @override
  void close({bool force = false}) {}
}

class _FakeMessaging implements PushMessaging {
  _FakeMessaging({this.granted = true, this.isAvailable = true});

  bool granted;
  String? current = 'token-aaaaaaaaaaaaaaaaaaaa';
  bool isAvailable;
  final refresh = StreamController<String>.broadcast();

  @override
  bool get available => isAvailable;
  @override
  Future<bool> requestPermission() async => granted;
  @override
  Future<String?> token() async => current;
  @override
  Stream<String> get tokenRefreshes => refresh.stream;
  @override
  Stream<PushData> get opened => const Stream.empty();
  @override
  Future<PushData?> launchData() async => null;
  @override
  Stream<PushData> get foreground => const Stream.empty();
}

void main() {
  late _Adapter adapter;
  late Dio dio;

  setUp(() {
    adapter = _Adapter();
    dio = Dio(BaseOptions(baseUrl: 'http://api.test/api/v1'))..httpClientAdapter = adapter;
  });

  Map<String, dynamic> body(RequestOptions o) => o.data as Map<String, dynamic>;

  test('registers the token once permission is granted, for the right app', () async {
    final registrar = PushRegistrar(dio, _FakeMessaging());
    await registrar.register('customer');
    expect(adapter.requests.single.method, 'PUT');
    expect(adapter.requests.single.path, '/devices/token');
    expect(body(adapter.requests.single)['app'], 'customer');
    expect(body(adapter.requests.single)['token'], 'token-aaaaaaaaaaaaaaaaaaaa');
    expect(registrar.currentToken, isNotNull);
  });

  test('sends nothing when permission is denied or Firebase is not configured', () async {
    await PushRegistrar(dio, _FakeMessaging(granted: false)).register('customer');
    await PushRegistrar(dio, _FakeMessaging(isAvailable: false)).register('owner');
    await PushRegistrar(dio, const NoopPushMessaging()).register('owner');
    expect(adapter.requests, isEmpty);
  });

  test('a refreshed token is registered again', () async {
    final messaging = _FakeMessaging();
    final registrar = PushRegistrar(dio, messaging);
    await registrar.register('owner');
    messaging.refresh.add('token-bbbbbbbbbbbbbbbbbbbb');
    await Future<void>.delayed(const Duration(milliseconds: 20));
    expect(adapter.requests.length, 2);
    expect(body(adapter.requests.last)['token'], 'token-bbbbbbbbbbbbbbbbbbbb');
    expect(body(adapter.requests.last)['app'], 'owner');
  });

  test('sign-out removes the token from the backend and stops listening', () async {
    final messaging = _FakeMessaging();
    final registrar = PushRegistrar(dio, messaging);
    await registrar.register('customer');
    await registrar.unregister();
    expect(adapter.requests.last.path, '/devices/token/remove');
    expect(body(adapter.requests.last)['token'], 'token-aaaaaaaaaaaaaaaaaaaa');
    expect(registrar.currentToken, isNull);
    messaging.refresh.add('token-cccccccccccccccccccc');
    await Future<void>.delayed(Duration.zero);
    expect(adapter.requests.length, 2); // nothing sent after sign-out
  });

  test('a backend failure never throws into sign-in', () async {
    adapter.fail = true;
    final registrar = PushRegistrar(dio, _FakeMessaging());
    await registrar.register('customer');
    await registrar.unregister();
    expect(jsonEncode(adapter.requests.map((r) => r.path).toList()), isNotEmpty);
  });

  test('unregister without a registered token does nothing', () async {
    await PushRegistrar(dio, _FakeMessaging()).unregister();
    expect(adapter.requests, isEmpty);
  });
}
