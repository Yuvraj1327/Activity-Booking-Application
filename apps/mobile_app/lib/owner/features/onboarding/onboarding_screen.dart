import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
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
  const _Page(this.icon, this.title, this.body);
  final IconData icon;
  final String title;
  final String body;
}

const _pages = [
  _Page(Icons.add_business_rounded, 'List your venue',
      'Create a listing with photos, sports, facilities and pricing. Save it as a draft and publish when it is ready.'),
  _Page(Icons.groups_rounded, 'Reach more customers',
      'Players across your city discover published venues by sport, price and location.'),
  _Page(Icons.event_note_rounded, 'Manage bookings',
      'Set your opening hours now. Incoming bookings will appear here once online booking launches.'),
  _Page(Icons.account_balance_wallet_rounded, 'Track earnings',
      'Payments and payouts will be tracked here once online payments are switched on.'),
  _Page(Icons.trending_up_rounded, 'Grow your business',
      'Follow ratings and venue performance, and keep your listings fresh.'),
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
    await ref.read(ownerOnboardingDoneProvider.notifier).complete();
    if (mounted) context.go(next);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final last = _index == _pages.length - 1;
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            Align(
              alignment: Alignment.centerRight,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(0, 8, 12, 0),
                child: TextButton(
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
                    padding: const EdgeInsets.symmetric(horizontal: 32),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Container(
                          width: 168,
                          height: 168,
                          decoration: BoxDecoration(color: Theme.of(context).colorScheme.primaryContainer, shape: BoxShape.circle),
                          child: Icon(page.icon, size: 76, color: theme.colorScheme.primary),
                        ),
                        const SizedBox(height: 40),
                        Text(page.title, style: theme.textTheme.headlineMedium, textAlign: TextAlign.center),
                        const SizedBox(height: 12),
                        Text(page.body, style: theme.textTheme.bodyLarge?.copyWith(color: ZuruvColors.textSecondary), textAlign: TextAlign.center),
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
                      color: i == _index ? theme.colorScheme.primary : Theme.of(context).colorScheme.outline,
                      borderRadius: BorderRadius.circular(4),
                    ),
                  ),
              ],
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(Gap.page + 4, 28, Gap.page + 4, 24),
              child: FilledButton(
                onPressed: () {
                  if (last) {
                    _finish(next: '/owner/dashboard');
                  } else {
                    _controller.nextPage(duration: const Duration(milliseconds: 280), curve: Curves.easeOut);
                  }
                },
                child: Text(last ? 'Get Started' : 'Next'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
