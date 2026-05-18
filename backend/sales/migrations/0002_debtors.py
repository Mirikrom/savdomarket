# Generated for qarzga savdo

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0001_initial"),
        ("shops", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Debtor",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_active", models.BooleanField(default=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("name", models.CharField(max_length=255)),
                ("phone", models.CharField(blank=True, max_length=32)),
                ("note", models.CharField(blank=True, max_length=500)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="debtors",
                        to="shops.organization",
                    ),
                ),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.AddField(
            model_name="sale",
            name="debtor",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="sales",
                to="sales.debtor",
            ),
        ),
        migrations.CreateModel(
            name="DebtPayment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                (
                    "method",
                    models.CharField(
                        choices=[("cash", "Cash"), ("card", "Card"), ("transfer", "Transfer")],
                        default="cash",
                        max_length=16,
                    ),
                ),
                ("note", models.CharField(blank=True, max_length=255)),
                (
                    "branch",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="debt_payments",
                        to="shops.branch",
                    ),
                ),
                (
                    "debtor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="payments",
                        to="sales.debtor",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="debt_payments",
                        to="shops.organization",
                    ),
                ),
                (
                    "received_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="debt_payments_received",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="debtor",
            index=models.Index(fields=["organization", "name"], name="sales_debtor_org_name_idx"),
        ),
        migrations.AddIndex(
            model_name="sale",
            index=models.Index(fields=["organization", "debtor"], name="sales_sale_org_debtor_idx"),
        ),
        migrations.AddIndex(
            model_name="debtpayment",
            index=models.Index(fields=["organization", "debtor", "created_at"], name="sales_debtpay_org_idx"),
        ),
    ]
