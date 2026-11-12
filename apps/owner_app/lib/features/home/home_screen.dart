import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';

import '../../core/providers.dart';

/// Signed-in landing placeholder. Product screens arrive in later steps.
class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final auth = ref.watch(authControllerProvider);
    final health = ref.watch(backendHealthProvider);
    final profile = auth is Authenticated ? auth.profile : null;

    return Scaffold(
      appBar: AppBar(
        title: const Text('ZURUV Owner'),
        actions: [
          IconButton(
            tooltip: 'Sign out',
            icon: const Icon(Icons.logout),
            onPressed: () => ref.read(authControllerProvider.notifier).signOut(),
          ),
        ],
      ),
      body: SafeArea(
        child: ResponsivePage(
          child: ListView(
            padding: const EdgeInsets.symmetric(vertical: 24),
            children: [
              Text('Hello, ${profile?.fullName ?? ''}', style: theme.textTheme.headlineMedium),
              const SizedBox(height: 8),
              Text('Signed in as a ${profile?.role.label ?? ''}. Product screens arrive in later steps.',
                  style: theme.textTheme.bodySmall),
              const SizedBox(height: 24),
              health.when(
                loading: () => const SizedBox(height: 80, child: LoadingView()),
                error: (e, _) => ErrorView.fromError(e, onRetry: () => ref.invalidate(backendHealthProvider)),
                data: (data) => Card(
                  child: ListTile(
                    leading: Icon(
                      data['status'] == 'ok' ? Icons.check_circle : Icons.info_outline,
                      color: data['status'] == 'ok' ? ZuruvColors.success : ZuruvColors.textSecondary,
                    ),
                    title: const Text('Backend'),
                    subtitle: Text('Reachable · database: ${(data['database'] as Map?)?['status'] ?? 'unknown'}'),
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
