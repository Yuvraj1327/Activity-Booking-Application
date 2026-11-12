import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/models.dart';
import '../auth/providers.dart';
import '../auth/state.dart';
import 'push_service.dart';

/// Wrap the app with this. It registers the device token once the user is signed in, and turns a
/// notification tap into navigation via [onOpen] (called with the push data; ids only).
///
/// Taps are handled for all three launch states: app open (foreground refresh), app in the
/// background (`opened`) and app launched from a terminated state (`launchData`).
class PushBootstrap extends ConsumerStatefulWidget {
  const PushBootstrap({super.key, required this.child, required this.onOpen, this.onForeground});

  final Widget child;
  final void Function(PushData data) onOpen;

  /// Optional: called when a push arrives while the app is open (e.g. to refresh badges).
  final void Function(PushData data)? onForeground;

  @override
  ConsumerState<PushBootstrap> createState() => _PushBootstrapState();
}

class _PushBootstrapState extends ConsumerState<PushBootstrap> {
  StreamSubscription<PushData>? _openedSub;
  StreamSubscription<PushData>? _foregroundSub;
  String? _registeredFor;

  @override
  void initState() {
    super.initState();
    final messaging = ref.read(pushMessagingProvider);
    _openedSub = messaging.opened.listen(widget.onOpen);
    _foregroundSub = messaging.foreground.listen((d) => widget.onForeground?.call(d));
    WidgetsBinding.instance.addPostFrameCallback((_) => _onAuth(ref.read(authControllerProvider)));
  }

  Future<void> _onAuth(AppAuthState auth) async {
    if (auth is! Authenticated) {
      _registeredFor = null;
      return;
    }
    if (_registeredFor == auth.profile.id) return;
    _registeredFor = auth.profile.id;
    final app = ref.read(expectedRoleProvider) == AppRole.owner ? 'owner' : 'customer';
    await ref.read(pushRegistrarProvider).register(app);
    final launch = await ref.read(pushMessagingProvider).launchData();
    if (launch != null && mounted) widget.onOpen(launch);
  }

  @override
  void dispose() {
    _openedSub?.cancel();
    _foregroundSub?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    ref.listen<AppAuthState>(authControllerProvider, (_, next) => _onAuth(next));
    return widget.child;
  }
}
