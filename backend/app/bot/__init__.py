"""Telegram bot process (``python -m app.bot``).

Runs separately from the API, but in the same code base, so it reuses the
models and services instead of calling the HTTP API with per-user tokens.
"""
