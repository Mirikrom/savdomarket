from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0006_debtor_due_date"),
    ]

    operations = [
        migrations.AddField(
            model_name="debtpayment",
            name="client_uuid",
            field=models.UUIDField(blank=True, db_index=True, editable=False, null=True),
        ),
        migrations.AddConstraint(
            model_name="debtpayment",
            constraint=models.UniqueConstraint(
                condition=models.Q(("client_uuid__isnull", False)),
                fields=("organization", "client_uuid"),
                name="uniq_debt_payment_client_uuid_per_org",
            ),
        ),
    ]
