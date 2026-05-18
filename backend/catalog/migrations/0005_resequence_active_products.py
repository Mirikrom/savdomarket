from django.db import migrations


def resequence_active_only(apps, schema_editor):
    """0004 barcha yozuvlarni ketma-ketlagan bo‘lishi mumkin — faol mahsulotlar 1 dan boshlansin."""
    Product = apps.get_model("catalog", "Product")
    Product.objects.exclude(is_active=True, deleted_at__isnull=True).update(sequence_number=0)
    org_ids = (
        Product.objects.filter(is_active=True, deleted_at__isnull=True)
        .order_by("organization_id")
        .values_list("organization_id", flat=True)
        .distinct()
    )
    for org_id in org_ids:
        rows = list(
            Product.objects.filter(
                organization_id=org_id,
                is_active=True,
                deleted_at__isnull=True,
            ).order_by("id")
        )
        for i, p in enumerate(rows, start=1):
            p.sequence_number = i
        Product.objects.bulk_update(rows, ["sequence_number"], batch_size=500)


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0004_product_sequence_number"),
    ]

    operations = [
        migrations.RunPython(resequence_active_only, migrations.RunPython.noop),
    ]
