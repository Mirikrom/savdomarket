"""Short-lived signed tokens used between OTP verification and final action.

These are *not* JWT access tokens — they are tiny signed payloads (using
Django's TimestampSigner) that prove "phone X was verified within the last
N minutes for purpose Y". They expire automatically and cannot be tampered
with because they're signed with SECRET_KEY.
"""

from __future__ import annotations

import json
from typing import Any

from django.core import signing
from rest_framework import serializers

REGISTRATION_TOKEN_TTL = 15 * 60  # 15 minutes
RESET_TOKEN_TTL = 15 * 60


def _issue(salt: str, payload: dict[str, Any]) -> str:
    return signing.TimestampSigner(salt=salt).sign_object(payload)


def _read(salt: str, token: str, max_age: int) -> dict[str, Any]:
    try:
        return signing.TimestampSigner(salt=salt).unsign_object(token, max_age=max_age)
    except signing.SignatureExpired:
        raise serializers.ValidationError(
            {"token": "Tasdiqlash muddati tugagan. Iltimos qayta urinib ko'ring."}
        )
    except (signing.BadSignature, json.JSONDecodeError):
        raise serializers.ValidationError(
            {"token": "Tasdiqlash kaliti noto'g'ri."}
        )


def issue_registration_token(phone: str) -> str:
    return _issue("auth.registration", {"phone": phone})


def read_registration_token(token: str) -> str:
    data = _read("auth.registration", token, REGISTRATION_TOKEN_TTL)
    phone = data.get("phone")
    if not phone:
        raise serializers.ValidationError({"token": "Tasdiqlash kaliti buzilgan."})
    return phone


def issue_reset_token(user_id: int) -> str:
    return _issue("auth.password_reset", {"user_id": user_id})


def read_reset_token(token: str) -> int:
    data = _read("auth.password_reset", token, RESET_TOKEN_TTL)
    user_id = data.get("user_id")
    if not isinstance(user_id, int):
        raise serializers.ValidationError({"token": "Tasdiqlash kaliti buzilgan."})
    return user_id
