"""Avval soft-delete qilingan tashkilotlarni butunlay o‘chirish."""

from django.core.management.base import BaseCommand
from django.db import transaction

from shops.models import Organization
from shops.services.organization_purge import purge_organization


class Command(BaseCommand):
    help = "deleted_at to‘ldirilgan (eski soft-delete) tashkilotlarni bazadan butunlay olib tashlaydi."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Tasdiqlash (majburiy)",
        )

    def handle(self, *args, **options):
        if not options["confirm"]:
            self.stderr.write("Davom etish: --confirm")
            return

        qs = Organization.objects.filter(deleted_at__isnull=False)
        count = qs.count()
        if not count:
            self.stdout.write(self.style.SUCCESS("Soft-delete qilingan tashkilot yo‘q."))
            return

        with transaction.atomic():
            for org in qs.iterator():
                result = purge_organization(org)
                self.stdout.write(
                    f"O‘chirildi org_id={result['organization_id']}, "
                    f"users_removed={result['users_removed']}"
                )

        self.stdout.write(self.style.SUCCESS(f"Jami {count} ta tashkilot tozalandi."))
