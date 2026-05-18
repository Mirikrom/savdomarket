"""Pluggable SMS / messaging backends.

The active backend is configured via ``settings.SMS_BACKEND`` and must implement
``send(phone, message)``. In development the ``ConsoleSmsBackend`` is used so
no real money is spent — codes simply appear in the Django console.

For production switch ``SMS_BACKEND`` to ``EskizSmsBackend`` (or any other) and
provide credentials in env vars.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional

from django.conf import settings
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)


class SmsBackend(ABC):
    @abstractmethod
    def send(self, phone: str, message: str) -> None: ...


class ConsoleSmsBackend(SmsBackend):
    """Prints the message to the Django console. Use in development only."""

    def send(self, phone: str, message: str) -> None:
        banner = "=" * 60
        logger.warning(
            "\n%s\n[SMS:CONSOLE] To: %s\n%s\n%s\n",
            banner,
            phone,
            message,
            banner,
        )
        print(f"\n{banner}\n[SMS:CONSOLE] To: {phone}\n{message}\n{banner}\n", flush=True)


class EskizSmsBackend(SmsBackend):
    """Eskiz.uz integration.

    Requires:
        ESKIZ_EMAIL
        ESKIZ_PASSWORD
        ESKIZ_FROM (e.g. "4546" or your approved alpha-name)

    Tokens are cached on the backend instance for the process lifetime; for
    multi-worker deployments consider caching in Redis instead.
    """

    BASE_URL = "https://notify.eskiz.uz/api"

    def __init__(self):
        self._token: Optional[str] = None
        self.email = getattr(settings, "ESKIZ_EMAIL", "")
        self.password = getattr(settings, "ESKIZ_PASSWORD", "")
        self.sender = getattr(settings, "ESKIZ_FROM", "4546")

    def _login(self) -> str:
        import requests  # local import: only needed when this backend is active

        if not self.email or not self.password:
            raise RuntimeError("ESKIZ_EMAIL/ESKIZ_PASSWORD are not configured.")
        resp = requests.post(
            f"{self.BASE_URL}/auth/login",
            data={"email": self.email, "password": self.password},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        token = data.get("data", {}).get("token") or data.get("token")
        if not token:
            raise RuntimeError(f"Eskiz login response missing token: {data}")
        self._token = token
        return token

    def _get_token(self) -> str:
        return self._token or self._login()

    def send(self, phone: str, message: str) -> None:
        import requests

        token = self._get_token()
        clean_phone = phone.lstrip("+")
        try:
            resp = requests.post(
                f"{self.BASE_URL}/message/sms/send",
                data={"mobile_phone": clean_phone, "message": message, "from": self.sender},
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            if resp.status_code == 401:
                self._token = None
                token = self._get_token()
                resp = requests.post(
                    f"{self.BASE_URL}/message/sms/send",
                    data={
                        "mobile_phone": clean_phone,
                        "message": message,
                        "from": self.sender,
                    },
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10,
                )
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001 — surface any SMS failure
            logger.exception("Eskiz SMS send failed: %s", exc)
            raise


class TelegramBotBackend(SmsBackend):
    """Sends the code to the user via a Telegram bot.

    Each user must have linked their Telegram chat_id beforehand. This backend
    looks up the chat_id from the ``TelegramAccount`` model (not implemented in
    this baseline — left as an extension point).

    For now this backend simply logs a warning; replace with real implementation
    when you add Telegram linking.
    """

    def send(self, phone: str, message: str) -> None:
        logger.warning(
            "[SMS:TELEGRAM] Skipped — Telegram backend requires chat_id mapping. "
            "Phone=%s message=%s",
            phone,
            message,
        )


_backend_instance: Optional[SmsBackend] = None


def get_sms_backend() -> SmsBackend:
    """Return a singleton instance of the configured SMS backend."""
    global _backend_instance
    if _backend_instance is None:
        path = getattr(
            settings,
            "SMS_BACKEND",
            "accounts.services.sms.ConsoleSmsBackend",
        )
        backend_cls = import_string(path)
        _backend_instance = backend_cls()
    return _backend_instance


def send_sms(phone: str, message: str) -> None:
    """Convenience wrapper used by the OTP service."""
    get_sms_backend().send(phone, message)
