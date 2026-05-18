# Generated manually

from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0002_remove_product_uniq_sku_per_organization_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="cost_price",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0"),
                max_digits=12,
                verbose_name="Tan narxi",
            ),
        ),
    ]
