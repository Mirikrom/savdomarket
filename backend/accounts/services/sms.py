"""Pluggable SMS / messaging backends.

The active backend is configured via ``settings.SMS_BACKEND`` and must implement
``send(phone, message)``. In development the ``ConsoleSmsBackend`` is used so
no real money is spent — codes simply appear in the Django console.

For production use ``DevsmsBackend`` (devsms.uz) or ``EskizSmsBackend`` and
provide credentials in env vars.
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Optional

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


def _digits_phone(phone: str) -> str:
    """devsms.uz: 998901234567 (faqat raqamlar, + siz)."""
    return re.sub(r"\D", "", (phone or "").lstrip("+"))


class DevsmsBackend(SmsBackend):
    """devsms.uz — Bearer token bilan SMS yuborish.

    Sozlamalar (.env):
        DEVSMS_TOKEN   — kabinetdan olingan Bearer token
        DEVSMS_FROM    — jo‘natuvchi ID (default 4546)
        DEVSMS_API_URL — ixtiyoriy (default https://devsms.uz/api/send_sms.php)
        DEVSMS_CALLBACK_URL — ixtiyoriy holat callback
    """

    def __init__(self):
        self.api_url = getattr(
            settings,
            "DEVSMS_API_URL",
            "https://devsms.uz/api/send_sms.php",
        )
        self.token = (getattr(settings, "DEVSMS_TOKEN", "") or "").strip()
        self.sender = getattr(settings, "DEVSMS_FROM", "4546") or "4546"
        self.callback_url = (getattr(settings, "DEVSMS_CALLBACK_URL", "") or "").strip()

    def send(self, phone: str, message: str) -> None:
        import requests

        if not self.token:
            raise RuntimeError("DEVSMS_TOKEN is not configured.")

        payload: dict[str, Any] = {
            "phone": _digits_phone(phone),
            "message": message,
            "from": self.sender,
        }
        if self.callback_url:
            payload["callback_url"] = self.callback_url

        try:
            resp = requests.post(
                self.api_url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            logger.exception("devsms.uz SMS request failed: %s", exc)
            raise RuntimeError("SMS yuborib bo‘lmadi. Keyinroq qayta urinib ko‘ring.") from exc
        except ValueError as exc:
            logger.exception("devsms.uz invalid JSON response")
            raise RuntimeError("SMS provayderidan noto‘g‘ri javob keldi.") from exc

        if not data.get("success"):
            err_msg = data.get("message") or data.get("error") or "SMS yuborilmadi"
            logger.error("devsms.uz SMS rejected: %s payload=%s", err_msg, payload.get("phone"))
            raise RuntimeError(str(err_msg))

        logger.info(
            "devsms.uz SMS sent phone=%s sms_id=%s status=%s",
            payload.get("phone"),
            (data.get("data") or {}).get("sms_id"),
            (data.get("data") or {}).get("status"),
        )


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
    from rest_framework import serializers

    try:
        get_sms_backend().send(phone, message)
    except RuntimeError as exc:
        raise serializers.ValidationError({"detail": str(exc)}) from exc
