from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('conveniencia_bobesponjaApp', '0005_remove_sales_tax_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='products',
            name='overnight_price',
            field=models.FloatField(default=0),
        ),
    ]