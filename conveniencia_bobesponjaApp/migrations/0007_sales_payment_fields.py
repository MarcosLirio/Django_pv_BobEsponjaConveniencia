from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('conveniencia_bobesponjaApp', '0006_products_overnight_price'),
    ]

    operations = [
        migrations.AddField(
            model_name='sales',
            name='payment_methods',
            field=models.CharField(default='DINHEIRO', max_length=100),
        ),
        migrations.AddField(
            model_name='sales',
            name='payment_other_detail',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
    ]
