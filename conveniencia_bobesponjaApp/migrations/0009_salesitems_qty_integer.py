from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('conveniencia_bobesponjaApp', '0008_products_infinite_stock_salesitems_qty_float'),
    ]

    operations = [
        migrations.AlterField(
            model_name='salesitems',
            name='qty',
            field=models.IntegerField(default=0),
        ),
    ]