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

# Mijozga ko‘rsatiladigan umumiy xabar (texnik tafsilot API da emas)
SMS_ERROR_GENERIC = (
    "SMS hozir yuborib bo‘lmadi. Birozdan keyin qayta urinib ko‘ring. "
    "Muammo davom etsa, qo‘llab-quvvatlash bilan bog‘laning."
)


class SmsDeliveryError(Exception):
    """SMS yuborilmadi: mijozga qisqa xabar, logda to‘liq sabab."""

    def __init__(
        self,
        user_message: str,
        technical_detail: str = "",
        *,
        status_code: int | None = None,
    ):
        self.user_message = user_message
        self.technical_detail = (technical_detail or user_message).strip()
        self.status_code = status_code
        super().__init__(self.technical_detail)


def user_friendly_sms_error(
    technical: str,
    *,
    status_code: int | None = None,
) -> str:
    """Provayder/API xatosini foydalanuvchi uchun tushunarli o‘zbekcha matnga aylantiradi."""
    text = (technical or "").strip().lower()

    if status_code == 401 or any(
        k in text
        for k in ("unauthorized", "autentifikatsiya", "token", "авторизац")
    ):
        return (
            "SMS xizmati sozlamalari noto‘g‘ri. "
            "Iltimos, administratorga xabar bering."
        )

    if status_code == 403:
        return "SMS yuborish uchun ruxsat yo‘q. Administrator bilan bog‘laning."

    if status_code in (500, 502, 503, 504) or any(
        k in text
        for k in (
            "internal server",
            "server error",
            "bad gateway",
            "service unavailable",
            "gateway timeout",
            "server xatosi",
        )
    ):
        return (
            "SMS xizmati vaqtincha ishlamayapti. "
            "Bir necha daqiqadan keyin qayta urinib ko‘ring."
        )

    if any(
        k in text
        for k in (
            "timeout",
            "timed out",
            "connection",
            "connect",
            "network",
            "unreachable",
            "refused",
            "resolve",
            "ssl",
            "internet",
            "no route",
            "name or service not known",
        )
    ):
        return (
            "SMS serveriga ulanib bo‘lmadi. Internet yoki SMS xizmati vaqtincha "
            "ishlamasligi mumkin. Keyinroq qayta urinib ko‘ring."
        )

    if any(
        k in text
        for k in (
            "balans",
            "balance",
            "yetarli emas",
            "yetarli yo'q",
            "yetarli yo‘q",
            "qolmadi",
            "qolmagan",
            "insufficient",
            "недостаточно",
            "пополн",
            "to'ldir",
            "toldir",
            "pul",
            "кредит",
        )
    ):
        return (
            "SMS yuborish uchun xizmat balansi yetarli emas. "
            "Iltimos, keyinroq urinib ko‘ring yoki administratorga murojaat qiling."
        )

    if any(
        k in text
        for k in (
            "модерацию",
            "moderatsiya",
            "moderation",
            "шаблон",
            "shablon",
            "мои тексты",
            "nomaqbul",
            "bloklangan",
        )
    ):
        return (
            "SMS matni hali tasdiqlanmagan. "
            "Iltimos, administratorga xabar bering."
        )

    if any(k in text for k in ("telefon", "phone", "raqam", "номер", "invalid phone")):
        return "Telefon raqami noto‘g‘ri. Iltimos, raqamni tekshirib qayta kiriting."

    if any(
        k in text
        for k in ("limit", "ko'p", "ko‘p", "juda tez", "rate", "throttle", "1 daqiqa")
    ):
        return "Juda tez-tez kod so‘raldi. Biroz kutib, qayta urinib ko‘ring."

    if "devsms_token" in text or "not configured" in text:
        return "SMS xizmati sozlanmagan. Administrator bilan bog‘laning."

    if "telefon raqami noto" in text:
        return "Telefon raqami noto‘g‘ri. Iltimos, raqamni tekshirib qayta kiriting."

    return SMS_ERROR_GENERIC


def _log_sms_failure(phone: str, exc: SmsDeliveryError) -> None:
    from accounts.services.phone import mask_phone

    logger.error(
        "SMS delivery failed phone=%s status=%s user_message=%s technical=%s",
        mask_phone(phone),
        exc.status_code,
        exc.user_message,
        exc.technical_detail,
    )


def _raise_sms_error(
    phone: str,
    technical: str,
    *,
    status_code: int | None = None,
) -> None:
    user_msg = user_friendly_sms_error(technical, status_code=status_code)
    exc = SmsDeliveryError(user_msg, technical, status_code=status_code)
    _log_sms_failure(phone, exc)
    raise exc


# devsms.uz universal_otp shablon turlari (docs 1.1)
OTP_TEMPLATE_CONFIRM = 1
OTP_TEMPLATE_PASSWORD_RESET = 2
OTP_TEMPLATE_REGISTRATION = 3
OTP_TEMPLATE_LOGIN = 4


class SmsBackend(ABC):
    @abstractmethod
    def send(self, phone: str, message: str) -> None: ...

    def send_otp(self, phone: str, code: str, template_type: int) -> None:
        """OTP SMS. Devsms — tasdiqlangan universal shablon; boshqalar — erkin matn."""
        from accounts.services.otp import CODE_TTL_SECONDS

        minutes = max(1, CODE_TTL_SECONDS // 60)
        labels = {
            OTP_TEMPLATE_REGISTRATION: "ro'yxatdan o'tish",
            OTP_TEMPLATE_PASSWORD_RESET: "parolni tiklash",
            OTP_TEMPLATE_LOGIN: "tizimga kirish",
            OTP_TEMPLATE_CONFIRM: "amaliyotni tasdiqlash",
        }
        label = labels.get(template_type, "tasdiqlash")
        self.send(
            phone,
            f"SavdoPro: {label} kodingiz {code}. "
            f"Kod {minutes} daqiqa ichida amal qiladi.",
        )


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


def _devsms_auth_token(raw: str) -> str:
    """`.env` da faqat token yoki `Bearer ...` bo‘lishi mumkin."""
    token = (raw or "").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token


def _devsms_callback_url(raw: str) -> str:
    """Noto‘g‘ri yoki namuna callback URL yuborilmasin (400 sababi bo‘lishi mumkin)."""
    url = (raw or "").strip()
    if not url.startswith(("http://", "https://")):
        return ""
    lower = url.lower()
    if any(
        bad in lower
        for bad in ("your-domain", "example.com", "localhost", "127.0.0.1")
    ):
        return ""
    return url


def _devsms_service_name(raw: str) -> str:
    """2–50 belgi: harf, raqam, bo‘shliq, nuqta, tire (devsms docs)."""
    name = re.sub(r"[^\w\s.\-]", "", (raw or "").strip(), flags=re.ASCII)
    name = re.sub(r"\s+", " ", name).strip()[:50]
    return name if len(name) >= 2 else "SavdoPro"


def _devsms_error_body(resp) -> str:
    try:
        data = resp.json()
    except ValueError:
        return (resp.text or "").strip()[:500] or f"HTTP {resp.status_code}"
    return (
        data.get("error")
        or data.get("message")
        or (resp.text or "").strip()[:500]
        or f"HTTP {resp.status_code}"
    )


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
        self.token = _devsms_auth_token(getattr(settings, "DEVSMS_TOKEN", "") or "")
        self.sender = (getattr(settings, "DEVSMS_FROM", "") or "").strip()
        self.callback_url = _devsms_callback_url(
            getattr(settings, "DEVSMS_CALLBACK_URL", "") or ""
        )
        self.service_name = _devsms_service_name(
            getattr(settings, "DEVSMS_OTP_SERVICE_NAME", "SavdoPro") or "SavdoPro"
        )

    def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        import requests

        digits = payload.get("phone") or ""

        if not self.token:
            _raise_sms_error(digits, "DEVSMS_TOKEN is not configured.")

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
            if not resp.ok:
                err_detail = _devsms_error_body(resp)
                logger.error(
                    "devsms.uz HTTP %s phone=%s response_body=%s api_error=%s payload_keys=%s",
                    resp.status_code,
                    digits,
                    resp.text[:2000],
                    err_detail,
                    list(payload.keys()),
                )
                _raise_sms_error(
                    digits,
                    err_detail,
                    status_code=resp.status_code,
                )

            data = resp.json()
        except SmsDeliveryError:
            raise
        except requests.Timeout as exc:
            logger.exception(
                "devsms.uz timeout phone=%s url=%s",
                digits,
                self.api_url,
            )
            _raise_sms_error(digits, f"timeout: {exc}")
        except requests.ConnectionError as exc:
            logger.exception(
                "devsms.uz connection error phone=%s url=%s detail=%s",
                digits,
                self.api_url,
                exc,
            )
            _raise_sms_error(digits, f"connection: {exc}")
        except requests.RequestException as exc:
            if getattr(exc, "response", None) is not None:
                err_detail = _devsms_error_body(exc.response)
                status = exc.response.status_code
                logger.error(
                    "devsms.uz request error phone=%s status=%s body=%s detail=%s",
                    digits,
                    status,
                    exc.response.text[:2000],
                    err_detail,
                )
                _raise_sms_error(digits, err_detail, status_code=status)
            logger.exception("devsms.uz SMS request failed phone=%s", digits)
            _raise_sms_error(digits, str(exc))
        except ValueError as exc:
            logger.exception(
                "devsms.uz invalid JSON phone=%s raw=%s",
                digits,
                getattr(resp, "text", "")[:500],
            )
            _raise_sms_error(digits, f"invalid JSON response: {exc}")

        if not data.get("success"):
            err_msg = data.get("message") or data.get("error") or "SMS yuborilmadi"
            logger.error(
                "devsms.uz SMS rejected phone=%s error=%s response=%s",
                digits,
                err_msg,
                data,
            )
            _raise_sms_error(digits, str(err_msg))

        return data

    def send(self, phone: str, message: str) -> None:
        digits = _digits_phone(phone)
        if len(digits) < 9:
            _raise_sms_error(digits or phone, "Telefon raqami noto‘g‘ri.")

        payload: dict[str, Any] = {
            "phone": digits,
            "message": message,
        }
        if self.sender:
            payload["from"] = self.sender
        if self.callback_url:
            payload["callback_url"] = self.callback_url

        data = self._request(payload)
        logger.info(
            "devsms.uz SMS sent phone=%s sms_id=%s status=%s",
            digits,
            (data.get("data") or {}).get("sms_id"),
            (data.get("data") or {}).get("status"),
        )

    def send_otp(self, phone: str, code: str, template_type: int) -> None:
        """Eskiz universal OTP shabloni — alohida moderatsiya shart emas."""
        digits = _digits_phone(phone)
        if len(digits) < 9:
            _raise_sms_error(digits or phone, "Telefon raqami noto‘g‘ri.")

        otp = re.sub(r"\D", "", str(code))
        if not (4 <= len(otp) <= 8):
            _raise_sms_error(digits, "OTP kodi noto‘g‘ri.")

        payload: dict[str, Any] = {
            "phone": digits,
            "type": "universal_otp",
            "template_type": template_type,
            "service_name": self.service_name,
            "otp_code": otp,
        }
        if self.callback_url:
            payload["callback_url"] = self.callback_url

        data = self._request(payload)
        logger.info(
            "devsms.uz universal_otp phone=%s template=%s sms_id=%s",
            digits,
            template_type,
            (data.get("data") or {}).get("sms_id"),
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


def _validation_error_from_sms(phone: str, exc: Exception):
    from rest_framework import serializers

    if isinstance(exc, SmsDeliveryError):
        raise serializers.ValidationError({"detail": exc.user_message}) from exc

    technical = str(exc).strip() or repr(exc)
    logger.exception("SMS unexpected error phone=%s technical=%s", phone, technical)
    user_msg = user_friendly_sms_error(technical)
    raise serializers.ValidationError({"detail": user_msg}) from exc


def send_sms(phone: str, message: str) -> None:
    """Erkin matnli SMS (Eskiz moderatsiyasi kerak bo‘lishi mumkin)."""
    try:
        get_sms_backend().send(phone, message)
    except Exception as exc:
        _validation_error_from_sms(phone, exc)


def send_otp_sms(phone: str, code: str, template_type: int) -> None:
    """OTP SMS — Devsms universal shablon yoki boshqa backend erkin matn."""
    try:
        get_sms_backend().send_otp(phone, code, template_type)
    except Exception as exc:
        _validation_error_from_sms(phone, exc)
