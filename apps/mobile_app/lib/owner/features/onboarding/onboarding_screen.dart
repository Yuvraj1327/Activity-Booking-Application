import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:zuruv/core/constants/tokens.dart';
import 'package:zuruv/core/storage/preferences.dart';

/// Whether the owner intro has been completed on this device. Shown once, right after an owner
/// first signs in (the general first-run intro is `core/onboarding`).
class OnboardingController extends Notifier<bool> {
  @override
  bool build() => ref.read(sharedPreferencesProvider).getBool(PrefKeys.ownerOnboardingDone) ?? false;

  Future<void> complete() async {
    state = true;
    await ref.read(sharedPreferencesProvider).setBool(PrefKeys.ownerOnboardingDone, true);
  }
}

final ownerOnboardingDoneProvider = NotifierProvider<OnboardingController, bool>(OnboardingController.new);

class _Page {
  const _Page(this.image, this.title, this.body);
  final String image;
  final String title;
  final String body;
}

const _pages = [
  _Page('assets/images/owner_onboarding/owner_onboarding_1_list_venue.png', 'List Your Venue',
      'Create a listing with photos, sports, facilities and pricing. Save it as a draft and publish when it\u2019s ready.'),
  _Page('assets/images/owner_onboarding/owner_onboarding_2_reach_customers.png', 'Reach More Customers',
      'Players across your city discover published venues by sport, price and location.'),
  _Page('assets/images/owner_onboarding/owner_onboarding_3_manage_bookings.png', 'Manage Bookings',
      'Set your opening hours now. Incoming bookings will appear here once online booking launches.'),
  _Page('assets/images/owner_onboarding/owner_onboarding_4_track_earnings.png', 'Track Earnings',
      'Payments and payouts will be tracked here once online payments are switched on.'),
  _Page('assets/images/owner_onboarding/owner_onboarding_5_grow_business.png', 'Grow Your Business',
      'Follow ratings and venue performance, and keep your listings fresh.'),
];

const _blue = Color(0xFF1456E0);
const _blueSoft = Color(0xFFC9D7F5);
const _ink = Color(0xFF111A2E);
const _muted = Color(0xFF4A5568);

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
    await ref.read(ownerOnboardingDoneProvider.notifier).complete();
    if (mounted) context.go(next);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final last = _index == _pages.length - 1;
    return Scaffold(
      backgroundColor: Colors.white,
      body: DecoratedBox(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Color(0xFFEAF2FF), Colors.white, Color(0xFFF2F7FF)],
          ),
        ),
        child: SafeArea(
          child: Column(
            children: [
              Align(
                alignment: Alignment.centerRight,
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(0, 8, 12, 0),
                  child: TextButton(
                    style: TextButton.styleFrom(foregroundColor: _blue, textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w500)),
                    onPressed: () => _finish(next: '/owner/dashboard'),
                    child: const Text('Skip'),
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
                    return Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 28),
                      child: Column(
                        children: [
                          Expanded(
                            flex: 5,
                            child: Padding(
                              padding: const EdgeInsets.only(top: 8, bottom: 16),
                              child: Image.asset(page.image, fit: BoxFit.contain, width: double.infinity),
                            ),
                          ),
                          Expanded(
                            flex: 4,
                            child: SingleChildScrollView(
                              child: Column(
                                children: [
                                  Text(
                                    page.title,
                                    textAlign: TextAlign.center,
                                    style: theme.textTheme.headlineMedium?.copyWith(color: _ink, fontWeight: FontWeight.w700),
                                  ),
                                  const SizedBox(height: 14),
                                  Text(
                                    page.body,
                                    textAlign: TextAlign.center,
                                    style: theme.textTheme.bodyLarge?.copyWith(color: _muted, height: 1.45),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ],
                      ),
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
                        color: i == _index ? _blue : _blueSoft,
                        borderRadius: BorderRadius.circular(4),
                      ),
                    ),
                ],
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(Gap.page + 4, 28, Gap.page + 4, 24),
                child: SizedBox(
                  width: double.infinity,
                  height: 54,
                  child: FilledButton(
                    style: FilledButton.styleFrom(
                      backgroundColor: _blue,
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(27)),
                      textStyle: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
                    ),
                    onPressed: () {
                      if (last) {
                        _finish(next: '/owner/dashboard');
                      } else {
                        _controller.nextPage(duration: const Duration(milliseconds: 280), curve: Curves.easeOut);
                      }
                    },
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(last ? 'Get Started' : 'Next'),
                        const SizedBox(width: 8),
                        Icon(last ? Icons.check_rounded : Icons.arrow_forward_rounded, size: 20),
                      ],
                    ),
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
