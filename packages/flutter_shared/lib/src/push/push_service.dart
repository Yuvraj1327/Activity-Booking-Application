import 'dart:async';

import 'package:dio/dio.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/providers.dart';

/// Data attached to a push (ids only, e.g. `booking_id`, `payment_id`, `type`).
typedef PushData = Map<String, String>;

/// The part of Firebase Cloud Messaging the apps use. Behind an interface so tests can fake it and
/// so an app without Firebase configuration keeps working (see [NoopPushMessaging]).
abstract class PushMessaging {
  /// False when Firebase is not configured for this build.
  bool get available;

  /// Asks the OS for notification permission. Returns whether it was granted.
  Future<bool> requestPermission();

  Future<String?> token();

  Stream<String> get tokenRefreshes;

  /// The user tapped a notification while the app was in the background.
  Stream<PushData> get opened;

  /// The user tapped a notification that launched the app from a terminated state.
  Future<PushData?> launchData();

  /// A push arrived while the app is open.
  Stream<PushData> get foreground;
}

class NoopPushMessaging implements PushMessaging {
  const NoopPushMessaging();

  @override
  bool get available => false;
  @override
  Future<bool> requestPermission() async => false;
  @override
  Future<String?> token() async => null;
  @override
  Stream<String> get tokenRefreshes => const Stream.empty();
  @override
  Stream<PushData> get opened => const Stream.empty();
  @override
  Future<PushData?> launchData() async => null;
  @override
  Stream<PushData> get foreground => const Stream.empty();
}

PushData _data(RemoteMessage m) => m.data.map((k, v) => MapEntry(k, v.toString()));

class FirebasePushMessaging implements PushMessaging {
  FirebasePushMessaging._(this._fm);

  final FirebaseMessaging _fm;

  /// Initialises Firebase from the native config files (google-services.json on Android,
  /// GoogleService-Info.plist on iOS). If they are missing, returns a no-op so the app still runs.
  static Future<PushMessaging> init() async {
    try {
      await Firebase.initializeApp();
      return FirebasePushMessaging._(FirebaseMessaging.instance);
    } catch (e) {
      debugPrint('Push notifications disabled: Firebase is not configured for this build.');
      return const NoopPushMessaging();
    }
  }

  @override
  bool get available => true;

  @override
  Future<bool> requestPermission() async {
    final s = await _fm.requestPermission();
    return s.authorizationStatus == AuthorizationStatus.authorized ||
        s.authorizationStatus == AuthorizationStatus.provisional;
  }

  @override
  Future<String?> token() => _fm.getToken();

  @override
  Stream<String> get tokenRefreshes => _fm.onTokenRefresh;

  @override
  Stream<PushData> get opened => FirebaseMessaging.onMessageOpenedApp.map(_data);

  @override
  Future<PushData?> launchData() async {
    final m = await _fm.getInitialMessage();
    return m == null ? null : _data(m);
  }

  @override
  Stream<PushData> get foreground => FirebaseMessaging.onMessage.map(_data);
}

/// Overridden in `main()` with the result of [FirebasePushMessaging.init]; tests override it too.
final pushMessagingProvider = Provider<PushMessaging>((ref) => const NoopPushMessaging());

/// Registers this device's token with the backend (`PUT /devices/token`), keeps it fresh when FCM
/// rotates it, and removes it on sign-out so a signed-out phone stops receiving that user's pushes.
class PushRegistrar {
  PushRegistrar(this._dio, this._messaging);

  final Dio _dio;
  final PushMessaging _messaging;
  String? _token;
  StreamSubscription<String>? _refresh;

  String? get currentToken => _token;

  static String get _platform => defaultTargetPlatform == TargetPlatform.iOS ? 'ios' : 'android';

  /// [app] is 'customer' or 'owner'. Safe to call repeatedly. Never throws.
  Future<void> register(String app) async {
    if (!_messaging.available) return;
    try {
      if (!await _messaging.requestPermission()) return;
      final t = await _messaging.token();
      if (t == null || t.isEmpty) return;
      await _send(t, app);
      // One app, two roles: a different account (e.g. customer after owner) may register next, so the
      // refresh listener is replaced each time and always reports the CURRENT role.
      await _refresh?.cancel();
      _refresh = _messaging.tokenRefreshes.listen((next) => _send(next, app));
    } catch (_) {
      // Push is a convenience; a failure here must never break sign-in.
    }
  }

  Future<void> _send(String token, String app) async {
    try {
      await _dio.put<void>('/devices/token', data: {'token': token, 'platform': _platform, 'app': app});
      _token = token;
    } catch (_) {
      // Retried on the next app start / token refresh.
    }
  }

  Future<void> unregister() async {
    final t = _token;
    _token = null;
    await _refresh?.cancel();
    _refresh = null;
    if (t == null) return;
    try {
      await _dio.post<void>('/devices/token/remove', data: {'token': t});
    } catch (_) {}
  }
}

final pushRegistrarProvider = Provider<PushRegistrar>((ref) {
  final registrar = PushRegistrar(ref.watch(apiClientProvider), ref.watch(pushMessagingProvider));
  ref.onDispose(() => registrar._refresh?.cancel());
  return registrar;
});
