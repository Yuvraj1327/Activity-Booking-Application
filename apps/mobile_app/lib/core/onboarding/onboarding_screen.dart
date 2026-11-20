import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:zuruv/core/storage/preferences.dart';

/// Whether the first-run intro has been completed on this device.
class OnboardingController extends Notifier<bool> {
  @override
  bool build() =>
      ref.read(sharedPreferencesProvider).getBool(PrefKeys.onboardingDone) ??
      false;

  Future<void> complete() async {
    state = true;
    await ref
        .read(sharedPreferencesProvider)
        .setBool(PrefKeys.onboardingDone, true);
  }
}

final onboardingDoneProvider =
    NotifierProvider<OnboardingController, bool>(OnboardingController.new);

class _Page {
  const _Page(this.image, this.title, this.body);
  final String image;
  final String title;
  final String body;
}

// Blue palette of the onboarding design (local to this screen).
const _blue = Color(0xFF0B4FD8);
const _blueDot = Color(0xFFC9D8F2);
const _ink = Color(0xFF0F1B33);
const _muted = Color(0xFF4A5568);

const _pages = [
  _Page(
      'assets/images/onboarding/onboarding_1_discover.png',
      'Discover venues\nnear you',
      'Browse courts, turfs, gyms, pools and more in your city.'),
  _Page(
      'assets/images/onboarding/onboarding_2_find.png',
      'Find the perfect\nspot',
      'Search by sport, location, price and amenities.'),
  _Page('assets/images/onboarding/onboarding_3_book.png', 'Book in a few taps',
      'Check live availability, pick a time and pay securely.'),
  _Page('assets/images/onboarding/onboarding_4_play.png',
      'Play, book\nand repeat', 'Your one-stop app for all sports activities.'),
];

class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key});

  @override
  ConsumerState<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends ConsumerState<OnboardingScreen> {
  final _controller = PageController();
  int _index = 0;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _finish({required String next}) async {
    await ref.read(onboardingDoneProvider.notifier).complete();
    if (mounted) context.go(next);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final last = _index == _pages.length - 1;
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Color(0xFFEAF2FF), Color(0xFFF7FAFF)],
          ),
        ),
        child: SafeArea(
          child: Column(
            children: [
              Align(
                alignment: Alignment.centerRight,
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(0, 4, 16, 0),
                  child: TextButton(
                    onPressed: () => _finish(next: '/login'),
                    style: TextButton.styleFrom(foregroundColor: _blue),
                    child: const Text('Skip',
                        style: TextStyle(
                            fontWeight: FontWeight.w600, fontSize: 16)),
                  ),
                ),
              ),
              Expanded(
                child: PageView.builder(
                  controller: _controller,
                  itemCount: _pages.length,
                  onPageChanged: (i) => setState(() => _index = i),
                  itemBuilder: (context, i) {
                    final page = _pages[i];
                    return Column(
                      children: [
                        Expanded(
                          flex: 6,
                          child: Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 12),
                            child: Image.asset(
                              page.image,
                              fit: BoxFit.contain,
                              width: double.infinity,
                              semanticLabel: page.title.replaceAll('\n', ' '),
                            ),
                          ),
                        ),
                        Expanded(
                          flex: 3,
                          child: Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 32),
                            child: FittedBox(
                              fit: BoxFit.scaleDown,
                              child: SizedBox(
                                width: 320,
                                child: Column(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    const SizedBox(height: 16),
                                    Text(
                                      page.title,
                                      textAlign: TextAlign.center,
                                      style: theme.textTheme.headlineMedium
                                          ?.copyWith(
                                              color: _ink,
                                              fontWeight: FontWeight.w800,
                                              height: 1.2,
                                              fontSize: 28),
                                    ),
                                    const SizedBox(height: 12),
                                    Text(
                                      page.body,
                                      textAlign: TextAlign.center,
                                      style: theme.textTheme.bodyMedium
                                          ?.copyWith(
                                              color: _muted,
                                              fontSize: 15,
                                              height: 1.45),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ),
                        ),
                      ],
                    );
                  },
                ),
              ),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  for (var i = 0; i < _pages.length; i++)
                    AnimatedContainer(
                      duration: const Duration(milliseconds: 200),
                      margin: const EdgeInsets.symmetric(horizontal: 4),
                      width: i == _index ? 24 : 8,
                      height: 8,
                      decoration: BoxDecoration(
                        color: i == _index ? _blue : _blueDot,
                        borderRadius: BorderRadius.circular(4),
                      ),
                    ),
                ],
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(24, 24, 24, 20),
                child: SizedBox(
                  width: double.infinity,
                  height: 54,
                  child: FilledButton(
                    style: FilledButton.styleFrom(
                      backgroundColor: _blue,
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(14)),
                      textStyle: const TextStyle(
                          fontSize: 17, fontWeight: FontWeight.w600),
                    ),
                    onPressed: () {
                      if (last) {
                        _finish(next: '/register');
                      } else {
                        _controller.nextPage(
                            duration: const Duration(milliseconds: 280),
                            curve: Curves.easeOut);
                      }
                    },
                    child: Text(last ? 'Get Started' : 'Next'),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
