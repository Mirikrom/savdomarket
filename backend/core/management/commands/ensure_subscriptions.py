"""Faol Subscriptionsiz qolib ketgan tashkilotlarga Lite trial berish."""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from shops.models import Organization
from subscriptions.models import Plan, Subscription
from subscriptions.services import get_active_subscription


class Command(BaseCommand):
    help = "Subscription'siz tashkilotlarga 14-kunlik Lite trial qo‘shadi."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=14)
        parser.add_argument("--plan", default="lite", choices=["lite", "pro"])

    def handle(self, *args, **options):
        plan = Plan.objects.filter(code=options["plan"], is_active=True).first()
        if plan is None:
            self.stderr.write(self.style.ERROR(f"Plan {options['plan']} topilmadi."))
            return

        now = timezone.now()
        ends_at = now + timedelta(days=options["days"])
        created_count = 0
        skipped_count = 0

        for org in Organization.objects.filter(is_active=True):
            if get_active_subscription(org):
                skipped_count += 1
                continue
            Subscription.objects.create(
                organization=org,
                plan=plan,
                starts_at=now,
                ends_at=ends_at,
                status=Subscription.Status.ACTIVE,
                auto_renew=False,
            )
            created_count += 1
            self.stdout.write(self.style.SUCCESS(f"+ {org.name}: trial yaratildi"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Tugadi. Yaratildi: {created_count}, o‘tkazib yuborildi: {skipped_count}"
            )
        )
