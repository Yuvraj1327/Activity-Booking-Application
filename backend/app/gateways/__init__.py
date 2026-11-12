"""Adapters for outside providers (Razorpay, Firebase Cloud Messaging, Resend).

Each one sits behind a small Protocol so the services never import an SDK and tests can inject fakes.
Nothing here ever logs a secret, a signature or a full gateway payload.
"""
