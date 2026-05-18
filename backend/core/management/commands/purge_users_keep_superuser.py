"""Barcha foydalanuvchilarni o‘chiradi, faqat bitta (ko‘rsatilgan telefon) qoladi — superuser."""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from sales.models import Sale

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Barcha User yozuvlarini o‘chiradi (bittasidan tashqari). "
        "Sale.cashier (PROTECT) uchun savdolarni saqlanadigan akkauntga bog‘laydi. "
        "Xavfli: --confirm kerak."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--keep-phone",
            default=os.environ.get("SINGLE_SUPERUSER_PHONE", "+998935319409").strip(),
            help="Qolishi kerak bo‘lgan superuser telefoni",
        )
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Haqiqatan ham bajarishni tasdiqlash (majburiy)",
        )

    def handle(self, *args, **options):
        if not options["confirm"]:
            raise CommandError(
                "Bu buyruq barcha akkauntlarni (bittasidan tashqari) o‘chiradi. "
                "Davom etish uchun: python manage.py purge_users_keep_superuser --confirm"
            )

        phone = (options["keep_phone"] or "").strip()
        if not phone:
            raise CommandError("--keep-phone yoki SINGLE_SUPERUSER_PHONE bo‘sh.")

        with transaction.atomic():
            try:
                keep = User.objects.get(phone=phone)
            except User.DoesNotExist as exc:
                raise CommandError(
                    f"Telefon {phone} bo‘yicha foydalanuvchi yo‘q. Avval single_superuser bilan yarating."
                ) from exc

            keep.is_superuser = True
            keep.is_staff = True
            keep.is_active = True
            keep.save(update_fields=["is_superuser", "is_staff", "is_active"])

            other_ids = list(User.objects.exclude(pk=keep.pk).values_list("pk", flat=True))
            if other_ids:
                n_sales = Sale.objects.filter(cashier_id__in=other_ids).update(cashier=keep)
                if n_sales:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Savdolarda kassir {n_sales} ta yozuv {keep.phone} ga o‘tkazildi (PROTECT uchun)."
                        )
                    )

            deleted_summary = User.objects.exclude(pk=keep.pk).delete()
            total = deleted_summary[0]
            self.stdout.write(self.style.WARNING(f"O‘chirildi (jami yozuvlar, CASCADE bilan): {total}"))
            for model_label, cnt in sorted(deleted_summary[1].items(), key=lambda x: -x[1]):
                if cnt:
                    self.stdout.write(f"  - {model_label}: {cnt}")

        rest = User.objects.count()
        self.stdout.write(self.style.SUCCESS(f"Tugadi. User jadvalida {rest} ta qator (kutilgani: 1)."))
        if rest != 1:
            self.stderr.write(self.style.ERROR("Kutilmagan holat: User soni 1 emas."))
