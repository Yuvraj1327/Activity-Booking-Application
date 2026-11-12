import 'package:flutter/material.dart';

import '../network/api_exception.dart';

class ErrorView extends StatelessWidget {
  const ErrorView({super.key, required this.message, this.onRetry});

  /// Builds a user-safe message from any error.
  factory ErrorView.fromError(Object error, {Key? key, VoidCallback? onRetry}) {
    final message = error is ApiException ? error.message : 'Something went wrong.';
    return ErrorView(key: key, message: message, onRetry: onRetry);
  }

  final String message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.error_outline, size: 40, color: theme.colorScheme.error),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center, style: theme.textTheme.bodyMedium),
            if (onRetry != null) ...[
              const SizedBox(height: 16),
              OutlinedButton(
                onPressed: onRetry,
                style: OutlinedButton.styleFrom(minimumSize: const Size(140, 44)),
                child: const Text('Try again'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
