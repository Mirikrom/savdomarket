from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="stockmovement",
            name="client_uuid",
            field=models.UUIDField(blank=True, db_index=True, editable=False, null=True),
        ),
        migrations.AddConstraint(
            model_name="stockmovement",
            constraint=models.UniqueConstraint(
                condition=models.Q(("client_uuid__isnull", False)),
                fields=("organization", "client_uuid"),
                name="uniq_stock_movement_client_uuid_per_org",
            ),
        ),
    ]
