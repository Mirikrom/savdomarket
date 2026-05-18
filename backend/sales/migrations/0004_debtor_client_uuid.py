import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0003_sale_offline_sync"),
    ]

    operations = [
        migrations.AddField(
            model_name="debtor",
            name="client_uuid",
            field=models.UUIDField(blank=True, db_index=True, editable=False, null=True),
        ),
        migrations.AddConstraint(
            model_name="debtor",
            constraint=models.UniqueConstraint(
                condition=models.Q(("client_uuid__isnull", False)),
                fields=("organization", "client_uuid"),
                name="uniq_debtor_client_uuid_per_org",
            ),
        ),
    ]
