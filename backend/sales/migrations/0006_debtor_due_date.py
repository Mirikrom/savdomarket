from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0005_merge_20260518_1129"),
    ]

    operations = [
        migrations.AddField(
            model_name="debtor",
            name="due_date",
            field=models.DateField(blank=True, help_text="Qarz qaytarish muddati", null=True),
        ),
    ]
