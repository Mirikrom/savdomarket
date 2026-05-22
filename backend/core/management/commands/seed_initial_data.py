from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import OrganizationUser, Role, RolePermission, User
from accounts.role_policy import LEGACY_ROLE_CODES, OWNER_PERMISSIONS, SELLER_PERMISSIONS
from shops.models import Branch, Organization
from subscriptions.models import Plan, Subscription


DEFAULT_PERMISSIONS = {
    "owner": list(OWNER_PERMISSIONS),
    "seller": list(SELLER_PERMISSIONS),
}


class Command(BaseCommand):
    help = "Seed default plans, roles, permissions, and create bootstrap superuser."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="admin")
        parser.add_argument("--phone", default="+998900000000")
        parser.add_argument("--password", default="0102030405aA")
        parser.add_argument("--full-name", default="SavdoPro Owner")
        parser.add_argument("--org-name", default="SavdoPro Demo")
        parser.add_argument("--org-slug", default="savdopro-demo")
        parser.add_argument("--plan", default="pro", choices=["lite", "pro"])

    def handle(self, *args, **options):
        self._seed_plans()
        owner_role = self._seed_system_roles()
        organization, main_branch = self._seed_organization(options["org_name"], options["org_slug"])
        self._seed_subscription(organization, options["plan"])
        user = self._ensure_superuser(
            username=options["username"],
            phone=options["phone"],
            password=options["password"],
            full_name=options["full_name"],
        )
        self._ensure_membership(organization, user, owner_role, main_branch)
        self.stdout.write(self.style.SUCCESS("Seeding completed successfully."))

    def _seed_plans(self):
        Plan.objects.update_or_create(
            code=Plan.PlanCode.LITE,
            defaults={
                "name": "Lite",
                "price_monthly": 15,
                "max_users": 3,
                "max_products": 500,
                "max_branches": 1,
                "feature_flags": {
                    "products": True,
                    "batch_tracking": False,
                },
                "is_active": True,
            },
        )
        Plan.objects.update_or_create(
            code=Plan.PlanCode.PRO,
            defaults={
                "name": "Pro",
                "price_monthly": 49,
                "max_users": 30,
                "max_products": 10000,
                "max_branches": 20,
                "feature_flags": {
                    "products": True,
                    "batch_tracking": True,
                },
                "is_active": True,
            },
        )
        self.stdout.write(self.style.SUCCESS("Default plans are ready."))

    def _seed_system_roles(self):
        owner_role = None
        for code, permission_codes in DEFAULT_PERMISSIONS.items():
            display = {"owner": "Egasi (Owner)", "seller": "Sotuvchi"}.get(code, code.capitalize())
            role, _ = Role.objects.update_or_create(
                organization=None,
                code=code,
                defaults={
                    "name": display,
                    "description": f"Default {code} role",
                    "is_system": True,
                    "is_active": True,
                },
            )
            if code == "owner":
                owner_role = role
            role.permissions.exclude(permission_code__in=permission_codes).delete()
            existing_codes = set(role.permissions.values_list("permission_code", flat=True))
            to_create = [
                RolePermission(role=role, permission_code=perm)
                for perm in permission_codes
                if perm not in existing_codes
            ]
            if to_create:
                RolePermission.objects.bulk_create(to_create)

        for legacy in LEGACY_ROLE_CODES:
            Role.objects.filter(organization=None, code=legacy, is_system=True).update(
                is_active=False,
                deleted_at=timezone.now(),
            )

        self.stdout.write(self.style.SUCCESS("Default roles and permissions are ready."))
        return owner_role

    def _seed_organization(self, org_name, org_slug):
        organization, _ = Organization.objects.update_or_create(
            slug=org_slug,
            defaults={
                "name": org_name,
                "phone": "",
                "address": "",
                "is_active": True,
            },
        )
        main_branch, _ = Branch.objects.get_or_create(
            organization=organization,
            name="Main Branch",
            defaults={"is_main": True, "address": ""},
        )
        self.stdout.write(self.style.SUCCESS("Default organization and branch are ready."))
        return organization, main_branch

    def _seed_subscription(self, organization, plan_code):
        plan = Plan.objects.get(code=plan_code)
        now = timezone.now()
        Subscription.objects.update_or_create(
            organization=organization,
            status=Subscription.Status.ACTIVE,
            defaults={
                "plan": plan,
                "starts_at": now,
                "ends_at": now + timedelta(days=30),
                "auto_renew": True,
            },
        )
        self.stdout.write(self.style.SUCCESS("Default subscription is ready."))

    def _unique_username(self, desired: str, exclude_user_id=None) -> str:
        """username global unique — boshqa userda band bo‘lsa suffix qo‘shiladi."""
        base = (desired or "admin").strip() or "admin"
        candidate = base
        counter = 2
        qs = User.objects.all()
        if exclude_user_id:
            qs = qs.exclude(pk=exclude_user_id)
        while qs.filter(username=candidate).exists():
            candidate = f"{base}-{counter}"
            counter += 1
        return candidate

    def _ensure_superuser(self, username, phone, password, full_name):
        safe_username = self._unique_username(username)
        user, created = User.objects.get_or_create(
            phone=phone,
            defaults={
                "username": safe_username,
                "full_name": full_name,
                "email": "",
                "is_active": True,
                "is_staff": True,
                "is_superuser": True,
                "phone_verified_at": timezone.now(),
                "last_password_changed_at": timezone.now(),
            },
        )
        if created:
            user.set_password(password)
            user.save(update_fields=["password"])
            self.stdout.write(self.style.SUCCESS(f"Superuser created: {phone}"))
        else:
            user.username = self._unique_username(username, exclude_user_id=user.pk)
            user.full_name = full_name
            user.is_staff = True
            user.is_superuser = True
            user.phone_verified_at = user.phone_verified_at or timezone.now()
            user.last_password_changed_at = timezone.now()
            user.set_password(password)
            user.save(
                update_fields=[
                    "username",
                    "full_name",
                    "is_staff",
                    "is_superuser",
                    "phone_verified_at",
                    "last_password_changed_at",
                    "password",
                ]
            )
            self.stdout.write(self.style.SUCCESS(f"Superuser updated: {phone}"))
        return user

    def _ensure_membership(self, organization, user, owner_role, branch):
        OrganizationUser.objects.update_or_create(
            organization=organization,
            user=user,
            defaults={
                "role": owner_role,
                "branch": branch,
                "status": OrganizationUser.MembershipStatus.ACTIVE,
                "is_active": True,
            },
        )
        self.stdout.write(self.style.SUCCESS("Organization membership is ready."))
