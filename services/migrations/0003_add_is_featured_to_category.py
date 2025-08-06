# Generated manually to add is_featured field to Category model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0002_remove_addon_services_ad_categor_be2a2d_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='is_featured',
            field=models.BooleanField(default=False, db_index=True),
        ),
    ] 