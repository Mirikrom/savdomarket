from django.db import migrations, models


def backfill_sequence_numbers(apps, schema_editor):
    """Faqat faol mahsulotlar 1..n; qolganlari 0 (ketma-ketlik faol ro‘yxat bo‘yicha)."""
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
        ("catalog", "0003_product_cost_price"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="sequence_number",
            field=models.PositiveIntegerField(db_index=True, default=0),
        ),
        migrations.RunPython(backfill_sequence_numbers, migrations.RunPython.noop),
    ]
