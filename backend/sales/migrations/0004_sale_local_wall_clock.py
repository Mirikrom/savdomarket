# Savdo vaqtlari PC/Toshkent soatida (10:20), UTC (+00) emas.

from django.db import migrations


def _to_local_naive_timestamp(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    pairs = [
        ("sales_sale", "sold_at"),
        ("sales_sale", "created_at"),
        ("sales_sale", "updated_at"),
        ("sales_saleitem", "created_at"),
        ("sales_saleitem", "updated_at"),
        ("sales_payment", "paid_at"),
        ("sales_payment", "created_at"),
        ("sales_payment", "updated_at"),
    ]
    with schema_editor.connection.cursor() as cursor:
        for table, column in pairs:
            cursor.execute(
                f"""
                ALTER TABLE {table}
                ALTER COLUMN {column} TYPE timestamp without time zone
                USING ({column} AT TIME ZONE 'Asia/Tashkent');
                """
            )


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0003_sale_offline_sync"),
    ]

    operations = [
        migrations.RunPython(_to_local_naive_timestamp, migrations.RunPython.noop),
    ]
