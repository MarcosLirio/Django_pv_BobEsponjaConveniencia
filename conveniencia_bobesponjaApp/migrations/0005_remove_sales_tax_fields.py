from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('conveniencia_bobesponjaApp', '0004_sales_user'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='sales',
            name='tax',
        ),
        migrations.RemoveField(
            model_name='sales',
            name='tax_amount',
        ),
    ]