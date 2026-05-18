# Generated manually — sotuvchi/kassir uchun kirim va katalogni o'qish.

from django.db import migrations


PERMS = (
    "inventory.receive",
    "products.view",
    "catalog.view",
)


def forwards(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    RolePermission = apps.get_model("accounts", "RolePermission")
    for role in Role.objects.filter(code__in=("cashier", "seller")):
        existing = set(
            RolePermission.objects.filter(role=role).values_list("permission_code", flat=True)
        )
        for code in PERMS:
            if code not in existing:
                RolePermission.objects.create(role=role, permission_code=code)


def backwards(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    RolePermission = apps.get_model("accounts", "RolePermission")
    RolePermission.objects.filter(
        role__code__in=("cashier", "seller"),
        permission_code__in=PERMS,
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_alter_user_options"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
