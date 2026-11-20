import 'dart:async';
import 'dart:js_interop';

import 'package:web/web.dart' as web;

/// Injects the Maps JavaScript API on Flutter web, using the key from `.env` so it never sits in the
/// tracked `web/index.html`. Completes true once the script has loaded; false on failure/timeout.
Future<bool> loadWebMaps(String apiKey) {
  if (apiKey.isEmpty) return Future.value(false);
  final done = Completer<bool>();
  final script = web.document.createElement('script') as web.HTMLScriptElement
    ..src = 'https://maps.googleapis.com/maps/api/js?key=${Uri.encodeQueryComponent(apiKey)}'
    ..async = true;
  script.onload = ((web.Event _) {
    if (!done.isCompleted) done.complete(true);
  }).toJS;
  script.onerror = ((web.Event _) {
    if (!done.isCompleted) done.complete(false);
  }).toJS;
  web.document.head!.append(script);
  return done.future.timeout(const Duration(seconds: 10), onTimeout: () => false);
}
