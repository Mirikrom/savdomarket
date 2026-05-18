"""Django standart parol validatorlari o'rniga — xabarlar o'zbekcha."""

from django.contrib.auth.password_validation import (
    CommonPasswordValidator,
    MinimumLengthValidator,
    NumericPasswordValidator,
    UserAttributeSimilarityValidator,
)
from django.core.exceptions import ValidationError


class UzbekMinimumLengthValidator(MinimumLengthValidator):
    def get_error_message(self):
        return (
            f"Parol juda qisqa. Kamida {self.min_length} ta belgi bo‘lishi kerak."
        )

    def get_help_text(self):
        return f"Parol kamida {self.min_length} ta belgidan iborat bo‘lishi kerak."


class UzbekUserAttributeSimilarityValidator(UserAttributeSimilarityValidator):
    def validate(self, password, user=None):
        try:
            super().validate(password, user=user)
        except ValidationError:
            raise ValidationError(
                "Parol telefon, ism yoki boshqa akkaunt ma'lumotlariga juda o'xshash.",
                code="password_too_similar",
            ) from None


class UzbekCommonPasswordValidator(CommonPasswordValidator):
    def get_error_message(self):
        return "Bu parol juda keng tarqalgan. Boshqa, murakkabroq parol tanlang."

    def get_help_text(self):
        return "Juda keng tarqalgan parollardan foydalanmang."


class UzbekNumericPasswordValidator(NumericPasswordValidator):
    def get_error_message(self):
        return "Parol faqat raqamlardan iborat bo‘lmasligi kerak."

    def get_help_text(self):
        return "Parolda harflar yoki boshqa belgilar ham bo‘lsin."
