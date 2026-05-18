"""OTP (one-time password) issuing and verification.

Security properties:
- Codes are generated with ``secrets.randbelow`` (cryptographically secure).
- Only the hashed code is stored; the plaintext lives only inside the
  outgoing SMS and is dropped from memory after sending.
- Per-destination rate limit (1 code per ``MIN_INTERVAL_SECONDS``) and a
  daily cap (``DAILY_CAP``) prevent SMS bombing.
- ``max_attempts`` protects against brute-force guessing of the code itself.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from accounts.models import OtpCode

CODE_LENGTH = 6
CODE_TTL_SECONDS = 120
MIN_INTERVAL_SECONDS = 60
DAILY_CAP = 10
MAX_ATTEMPTS = 5


@dataclass
class OtpIssueResult:
    otp: OtpCode
    raw_code: str
    expires_in: int


def _generate_code() -> str:
    return f"{secrets.randbelow(10**CODE_LENGTH):0{CODE_LENGTH}d}"


def _enforce_rate_limit(destination: str, purpose: str) -> None:
    now = timezone.now()

    recent = (
        OtpCode.objects.filter(destination=destination, purpose=purpose)
        .order_by("-created_at")
        .first()
    )
    if recent and (now - recent.created_at).total_seconds() < MIN_INTERVAL_SECONDS:
        wait = MIN_INTERVAL_SECONDS - int((now - recent.created_at).total_seconds())
        raise serializers.ValidationError(
            {"detail": f"Iltimos {wait} soniyadan keyin qayta urinib ko'ring."}
        )

    today_count = OtpCode.objects.filter(
        destination=destination,
        purpose=purpose,
        created_at__gte=now - timedelta(days=1),
    ).count()
    if today_count >= DAILY_CAP:
        raise serializers.ValidationError(
            {"detail": "Bugun uchun kod yuborish limiti tugagan. Ertaga qayta urinib ko'ring."}
        )


def issue_otp(
    *,
    destination: str,
    purpose: str,
    channel: str = OtpCode.Channel.SMS,
    ip_address: str | None = None,
    user_agent: str = "",
) -> OtpIssueResult:
    """Generate, persist and return a fresh OTP code.

    The plaintext code is returned in the result so the caller can hand it off
    to the SMS provider. It is *not* persisted in the database.
    """
    _enforce_rate_limit(destination, purpose)

    OtpCode.objects.filter(
        destination=destination, purpose=purpose, used_at__isnull=True
    ).update(used_at=timezone.now())

    raw_code = _generate_code()
    otp = OtpCode(
        destination=destination,
        purpose=purpose,
        channel=channel,
        expires_at=timezone.now() + timedelta(seconds=CODE_TTL_SECONDS),
        max_attempts=MAX_ATTEMPTS,
        ip_address=ip_address,
        user_agent=user_agent or "",
    )
    otp.set_code(raw_code)
    otp.save()

    return OtpIssueResult(otp=otp, raw_code=raw_code, expires_in=CODE_TTL_SECONDS)


def verify_otp(*, destination: str, purpose: str, code: str) -> OtpCode:
    """Verify an OTP code, mutating attempt counters as side effects.

    Raises ``serializers.ValidationError`` on any failure case; returns the OTP
    instance (already marked used) on success.
    """
    otp = (
        OtpCode.objects.filter(
            destination=destination, purpose=purpose, used_at__isnull=True
        )
        .order_by("-created_at")
        .first()
    )
    if otp is None:
        raise serializers.ValidationError({"code": "Kod topilmadi yoki muddati tugagan."})
    if otp.is_expired:
        raise serializers.ValidationError({"code": "Kod muddati tugagan."})
    if otp.is_blocked:
        raise serializers.ValidationError(
            {"code": "Urinishlar soni ko'p. Yangi kod oling."}
        )

    if not otp.check_code(code or ""):
        otp.register_attempt()
        raise serializers.ValidationError({"code": "Kod noto'g'ri."})

    otp.mark_used()
    return otp
