"""Berilgan telefon (mijoz) va uning do‘konlarini bazadan butunlay o‘chirish."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import OrganizationUser
from accounts.services.phone import normalize_phone
from shops.models import Organization
from shops.services.organization_purge import purge_organization

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Telefon bo‘yicha mijoz akkauntini va bog‘liq barcha tashkilotlarni o‘chiradi. "
        "Qayta ro‘yxatdan o‘tish uchun."
    )

    def add_arguments(self, parser):
        parser.add_argument("--phone", required=True, help="Masalan: +998901234567")
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Tasdiqlash (majburiy)",
        )

    def handle(self, *args, **options):
        if not options["confirm"]:
            raise CommandError("Davom etish uchun --confirm qo‘shing.")

        phone = normalize_phone((options["phone"] or "").strip())
        if not phone:
            raise CommandError("Telefon noto‘g‘ri.")

        user = User.objects.filter(phone=phone).first()
        if not user:
            self.stdout.write(self.style.WARNING(f"User topilmadi: {phone}"))
            return

        if user.is_superuser:
            raise CommandError("Superuser o‘chirib bo‘lmaydi.")

        org_ids = set(
            OrganizationUser.objects.filter(user_id=user.pk).values_list(
                "organization_id", flat=True
            )
        )

        with transaction.atomic():
            for org in Organization.objects.filter(id__in=org_ids).iterator():
                self.stdout.write(f"Tozalash: {org.name} (id={org.id})")
                purge_organization(org)

            if User.objects.filter(pk=user.pk).exists():
                if OrganizationUser.objects.filter(user_id=user.pk).exists():
                    raise CommandError(
                        "Foydalanuvchi boshqa tashkilotda qolgan — qo‘lda tekshiring."
                    )
                user.delete()
                self.stdout.write(self.style.SUCCESS(f"User o‘chirildi: {phone}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Tugadi. Endi {phone} bilan ro‘yxatdan o‘tish mumkin."
            )
        )
