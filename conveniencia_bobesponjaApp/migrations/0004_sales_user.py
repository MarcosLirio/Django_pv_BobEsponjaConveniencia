from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('conveniencia_bobesponjaApp', '0003_add_quantity_to_products'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='sales',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name='sales', to=settings.AUTH_USER_MODEL),
        ),
    ]
