"""
REST API xabarlarida keng qo'llaniladigan inglizcha matnlarni o'zbekchaga o'girish.
To'liq mos keladigan qatorlar; qolganlari o'zgarishsiz qoladi.
"""

from __future__ import annotations

from rest_framework.views import exception_handler as drf_exception_handler

# DRF / SimpleJWT at English default locale
_EXACT: dict[str, str] = {
    # Asosiy
    "This field is required.": "Bu maydon majburiy.",
    "This field may not be blank.": "Bu maydon bo'sh bo'lmasligi kerak.",
    "This field may not be null.": "Bu maydon null bo'lmasligi kerak.",
    "Enter a valid email address.": "To'g'ri email manzilini kiriting.",
    "Enter a valid URL.": "To'g'ri URL kiriting.",
    "Enter a valid UUID.": "To'g'ri UUID kiriting.",
    "Enter a valid JSON object.": "To'g'ri JSON kiriting.",
    "Not a valid boolean.": "Ha/yo'q (boolean) qiymat kiriting.",
    "Not a valid integer.": "Butun son kiriting.",
    "Not a valid number.": "Raqam kiriting.",
    "Not a valid string.": "Matn kiriting.",
    "A valid number is required.": "To'g'ri raqam kiriting.",
    "A valid boolean is required.": "Mantiqiy qiymat (true/false) kiriting.",
    # Ruxsat / autentifikatsiya
    "You do not have permission to perform this action.": "Bu amalni bajarish uchun ruxsatingiz yo'q.",
    "Authentication credentials were not provided.": "Kirish ma'lumotlari yuborilmadi.",
    "Incorrect authentication credentials.": "Noto'g'ri login yoki parol.",
    "Token is invalid or expired": "Token yaroqsiz yoki muddati o'tgan.",
    # Umumiy
    "Not found.": "Topilmadi.",
    "Invalid input.": "Noto'g'ri ma'lumot.",
    "Malformed request.": "So'rov formati noto'g'ri.",
    "A server error occurred.": "Server xatoligi yuz berdi.",
}


def _translate_value(obj):
    if isinstance(obj, str):
        return _EXACT.get(obj, obj)
    if isinstance(obj, list):
        return [_translate_value(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _translate_value(v) for k, v in obj.items()}
    return obj


def uz_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is not None and hasattr(response, "data"):
        response.data = _translate_value(response.data)
    return response
