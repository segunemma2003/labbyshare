# Generated by Django 5.2.4 on 2025-07-22 10:02

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("regions", "0001_initial"),
        ("services", "0001_initial"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="addon",
            name="services_ad_categor_be2a2d_idx",
        ),
        migrations.AlterUniqueTogether(
            name="addon",
            unique_together=set(),
        ),
        migrations.AddField(
            model_name="addon",
            name="categories",
            field=models.ManyToManyField(
                blank=True, related_name="addons", to="services.category"
            ),
        ),
        migrations.AddField(
            model_name="addon",
            name="region",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="addons",
                to="regions.region",
            ),
        ),
        migrations.AddIndex(
            model_name="addon",
            index=models.Index(
                fields=["region", "is_active"], name="services_ad_region__88015b_idx"
            ),
        ),
        migrations.RemoveField(
            model_name="addon",
            name="category",
        ),
    ]
