"""Barcha superuser/staff ni olib tashlab, bitta akkauntni yagona superuser qiladi."""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Barcha foydalanuvchilardan is_superuser va is_staff ni olib tashlaydi, "
        "keyin berilgan telefon bo'yicha bitta superuser o'rnatadi. "
        "Parolni env yoki --password orqali bering (shell tarixiga tushmasligi uchun env afzal)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--phone",
            default=os.environ.get("SINGLE_SUPERUSER_PHONE", "").strip(),
            help="Telefon (USERNAME_FIELD), masalan +998935319409",
        )
        parser.add_argument(
            "--password",
            default=os.environ.get("SINGLE_SUPERUSER_PASSWORD", ""),
            help="Yangi parol",
        )
        parser.add_argument(
            "--full-name",
            default=os.environ.get("SINGLE_SUPERUSER_FULL_NAME", "Super Admin"),
            dest="full_name",
        )

    def handle(self, *args, **options):
        phone = (options["phone"] or "").strip()
        password = options["password"] or ""
        full_name = (options["full_name"] or "Super Admin").strip() or "Super Admin"

        if not phone:
            raise CommandError(
                "Telefon kerak: --phone yoki muhit o'zgaruvchisi SINGLE_SUPERUSER_PHONE"
            )
        if not password:
            raise CommandError(
                "Parol kerak: --password yoki muhit o'zgaruvchisi SINGLE_SUPERUSER_PASSWORD"
            )

        n = User.objects.all().update(is_superuser=False, is_staff=False)
        self.stdout.write(self.style.WARNING(f"Barcha akkauntlardan admin huquqi olib tashlandi ({n} ta)."))

        user, created = User.objects.get_or_create(
            phone=phone,
            defaults={
                "full_name": full_name,
                "is_active": True,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        user.full_name = full_name
        user.is_active = True
        user.is_staff = True
        user.is_superuser = True
        user.failed_login_attempts = 0
        user.locked_until = None
        user.set_password(password)
        user.last_password_changed_at = timezone.now()
        user.save()

        action = "yaratildi" if created else "yangilandi"
        su_count = User.objects.filter(is_superuser=True).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Yagona superuser {action}: phone={user.phone}, id={user.pk}, is_superuser={user.is_superuser}"
            )
        )
        if su_count != 1:
            self.stderr.write(self.style.WARNING(f"Diqqat: hozir {su_count} ta superuser bor (kutilgani: 1)."))
        else:
            self.stdout.write(self.style.SUCCESS("Superuserlar soni: 1 (to'g'ri)."))
