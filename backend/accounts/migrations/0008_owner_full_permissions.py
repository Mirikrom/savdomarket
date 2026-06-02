from django.db import migrations

from accounts.role_policy import OWNER_PERMISSIONS, SELLER_PERMISSIONS


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

    for code, perms in (("owner", OWNER_PERMISSIONS), ("seller", SELLER_PERMISSIONS)):
        role = Role.objects.filter(organization__isnull=True, code=code, is_system=True).first()
        if role:
            _sync_role_permissions(Role, RolePermission, role, perms)


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_three_roles_owner_seller"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
