import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0002_debtors"),
    ]

    operations = [
        migrations.AddField(
            model_name="sale",
            name="client_uuid",
            field=models.UUIDField(blank=True, db_index=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="sale",
            name="stock_conflict",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="sale",
            name="sold_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddConstraint(
            model_name="sale",
            constraint=models.UniqueConstraint(
                condition=models.Q(("client_uuid__isnull", False)),
                fields=("organization", "client_uuid"),
                name="uniq_sale_client_uuid_per_org",
            ),
        ),
    ]
