"""Delivery-channel providers.

Providers isolate outbound integrations (email/SMS) from notification persistence.
The active provider is chosen per call from settings, so swapping mock for a real
API requires configuration only — no code changes. Provider failures are logged
by the caller and never break order-status transactions.
"""
