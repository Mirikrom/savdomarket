from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0005_resequence_active_products"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="product",
            name="sequence_number",
        ),
    ]
