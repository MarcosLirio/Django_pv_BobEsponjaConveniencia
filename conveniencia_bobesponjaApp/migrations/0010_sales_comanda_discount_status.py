from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('conveniencia_bobesponjaApp', '0009_salesitems_qty_integer'),
    ]

    operations = [
        migrations.AddField(
            model_name='sales',
            name='comanda_code',
            field=models.CharField(blank=True, default='', max_length=40),
        ),
        migrations.AddField(
            model_name='sales',
            name='discount_amount',
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name='sales',
            name='discount_type',
            field=models.CharField(choices=[('VALUE', 'Valor'), ('PERCENT', 'Percentual')], default='VALUE', max_length=10),
        ),
        migrations.AddField(
            model_name='sales',
            name='discount_value',
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name='sales',
            name='status',
            field=models.CharField(choices=[('OPEN', 'Aberta'), ('CLOSED', 'Fechada')], default='CLOSED', max_length=10),
        ),
    ]