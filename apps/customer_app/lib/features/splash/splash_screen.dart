import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';

import '../../core/config/app_config.dart';

/// True once the branded splash has been shown for [AppConfig.splashDuration].
final splashDoneProvider = StateProvider<bool>((ref) => false);

/// Branded launch screen. The router keeps users here until the timer ends AND the stored
/// session has been checked with the API, then moves on to onboarding, login or home.
class BrandedSplashScreen extends ConsumerStatefulWidget {
  const BrandedSplashScreen({super.key});

  @override
  ConsumerState<BrandedSplashScreen> createState() => _BrandedSplashScreenState();
}

class _BrandedSplashScreenState extends ConsumerState<BrandedSplashScreen> {
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _timer = Timer(AppConfig.splashDuration, () {
      if (mounted) ref.read(splashDoneProvider.notifier).state = true;
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF5A44F0), ZuruvColors.customerPrimary, Color(0xFF2A1A9E)],
          ),
        ),
        child: Stack(
          fit: StackFit.expand,
          children: [
            // Subtle court-line artwork until licensed sports photography is supplied by design.
            const CustomPaint(painter: _CourtLinesPainter()),
            SafeArea(
              child: Center(
                child: TweenAnimationBuilder<double>(
                  tween: Tween(begin: 0, end: 1),
                  duration: const Duration(milliseconds: 700),
                  curve: Curves.easeOutCubic,
                  builder: (context, t, child) => Opacity(
                    opacity: t,
                    child: Transform.translate(offset: Offset(0, 16 * (1 - t)), child: child),
                  ),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        width: 84,
                        height: 84,
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(26),
                        ),
                        alignment: Alignment.center,
                        child: const Text(
                          'Z',
                          style: TextStyle(fontSize: 48, fontWeight: FontWeight.w900, color: ZuruvColors.customerPrimary),
                        ),
                      ),
                      const SizedBox(height: 20),
                      const Text(
                        'ZURUV',
                        style: TextStyle(fontSize: 36, letterSpacing: 6, fontWeight: FontWeight.w800, color: Colors.white),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Discover. Book. Play.',
                        style: TextStyle(fontSize: 16, color: Colors.white.withValues(alpha: 0.85)),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _CourtLinesPainter extends CustomPainter {
  const _CourtLinesPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = Colors.white.withValues(alpha: 0.07)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2;
    final w = size.width;
    final h = size.height;
    canvas.drawRRect(RRect.fromRectAndRadius(Rect.fromLTWH(w * 0.08, h * 0.12, w * 0.84, h * 0.76), const Radius.circular(24)), paint);
    canvas.drawLine(Offset(w * 0.08, h * 0.5), Offset(w * 0.92, h * 0.5), paint);
    canvas.drawCircle(Offset(w * 0.5, h * 0.5), math.min(w, h) * 0.16, paint);
    canvas.drawRect(Rect.fromLTWH(w * 0.28, h * 0.12, w * 0.44, h * 0.14), paint);
    canvas.drawRect(Rect.fromLTWH(w * 0.28, h * 0.74, w * 0.44, h * 0.14), paint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
