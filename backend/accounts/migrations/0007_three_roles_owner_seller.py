# Tashkilot: faqat owner + seller. Eski admin/moderator/cashier → seller.

from django.db import migrations
from django.utils import timezone

LEGACY_ROLE_CODES = ("admin", "moderator", "cashier")
OWNER_PERMISSIONS = (
    "users.manage",
    "roles.manage",
    "organization_users.manage",
    "branches.manage",
    "subscriptions.manage",
    "subscriptions.view_invoices",
    "catalog.manage",
    "products.manage",
    "inventory.manage",
    "sales.manage",
    "sales.view",
)
SELLER_PERMISSIONS = (
    "sales.manage",
    "sales.view",
    "catalog.manage",
    "catalog.view",
    "products.manage",
    "products.view",
    "inventory.receive",
)


def _sync_role_permissions(Role, RolePermission, role, codes):
    RolePermission.objects.filter(role=role).exclude(permission_code__in=codes).delete()
    existing = set(
        RolePermission.objects.filter(role=role).values_list("permission_code", flat=True)
    )
    for code in codes:
        if code not in existing:
            RolePermission.objects.create(role=role, permission_code=code)


def forwards(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    RolePermission = apps.get_model("accounts", "RolePermission")
    OrganizationUser = apps.get_model("accounts", "OrganizationUser")
    now = timezone.now()

    seller_role = Role.objects.filter(
        organization__isnull=True, code="seller", is_system=True
    ).first()
    if not seller_role:
        seller_role = Role.objects.create(
            organization=None,
            code="seller",
            name="Sotuvchi",
            description="Default seller role",
            is_system=True,
            is_active=True,
        )

    owner_role = Role.objects.filter(
        organization__isnull=True, code="owner", is_system=True
    ).first()

    _sync_role_permissions(Role, RolePermission, seller_role, SELLER_PERMISSIONS)
    if owner_role:
        _sync_role_permissions(Role, RolePermission, owner_role, OWNER_PERMISSIONS)

    for legacy in LEGACY_ROLE_CODES:
        Role.objects.filter(organization__isnull=True, code=legacy, is_system=True).update(
            is_active=False,
            deleted_at=now,
        )

    if seller_role:
        OrganizationUser.objects.filter(
            role__code__in=LEGACY_ROLE_CODES,
        ).update(role_id=seller_role.id)


def backwards(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Role.objects.filter(
        organization__isnull=True,
        code__in=["admin", "moderator", "cashier"],
        is_system=True,
    ).update(is_active=True, deleted_at=None)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0006_cashier_seller_catalog_inventory_view"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
