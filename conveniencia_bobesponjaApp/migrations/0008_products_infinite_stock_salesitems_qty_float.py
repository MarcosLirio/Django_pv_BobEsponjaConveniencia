from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('conveniencia_bobesponjaApp', '0007_sales_payment_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='products',
            name='infinite_stock',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='salesitems',
            name='qty',
            field=models.FloatField(default=0),
        ),
    ]
