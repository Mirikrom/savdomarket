"""Phone number normalization and validation (Uzbekistan-first, but generic)."""

import re

from rest_framework import serializers

PHONE_REGEX = re.compile(r"^\+?[0-9]{9,15}$")
UZ_PREFIX = "+998"


def normalize_phone(raw: str) -> str:
    """Return E.164-style phone number.

    Rules (Uzbekistan defaults, easy to extend):
    - Strip spaces, dashes, parentheses.
    - 9-digit input (e.g. "901234567") -> assume Uzbek, prepend +998.
    - 12-digit input starting with 998 -> add leading +.
    - Already starts with + -> keep as is.
    """
    if raw is None:
        raise serializers.ValidationError({"phone": "Telefon raqami kiritilmagan."})

    cleaned = re.sub(r"[\s\-()]", "", str(raw))

    if not cleaned:
        raise serializers.ValidationError({"phone": "Telefon raqami kiritilmagan."})

    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]

    if not cleaned.startswith("+"):
        if len(cleaned) == 9 and cleaned.isdigit():
            cleaned = UZ_PREFIX + cleaned
        elif len(cleaned) == 12 and cleaned.startswith("998"):
            cleaned = "+" + cleaned
        elif cleaned.isdigit() and 10 <= len(cleaned) <= 15:
            cleaned = "+" + cleaned

    if not PHONE_REGEX.match(cleaned):
        raise serializers.ValidationError(
            {"phone": "Telefon raqami noto'g'ri formatda. Masalan: +998901234567"}
        )

    return cleaned


def mask_phone(phone: str) -> str:
    """Mask middle digits for safe display: +998 90 *** ** 67."""
    if not phone:
        return ""
    if len(phone) <= 6:
        return phone
    return f"{phone[:5]}***{phone[-2:]}"
