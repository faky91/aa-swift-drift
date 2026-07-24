"""Rename the "Hive" label to "Wormhole" and add the JumpBridge model."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("eve_sde", "0001_initial"),
        ("swiftdrift", "0002_drifterwormhole_bookmark"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="drifterwormhole",
            name="hive",
            field=models.CharField(
                choices=[
                    ("barbican", "Barbican"),
                    ("conflux", "Conflux"),
                    ("redoubt", "Redoubt"),
                    ("sentinel", "Sentinel"),
                    ("vidette", "Vidette"),
                ],
                max_length=16,
                verbose_name="Wormhole",
            ),
        ),
        migrations.CreateModel(
            name="JumpBridge",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "structure_name",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=100,
                        verbose_name="Structure name",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        editable=False,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "from_system",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="eve_sde.solarsystem",
                        verbose_name="From system",
                    ),
                ),
                (
                    "to_system",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="eve_sde.solarsystem",
                        verbose_name="To system",
                    ),
                ),
            ],
            options={
                "verbose_name": "Jump Bridge",
                "verbose_name_plural": "Jump Bridges",
                "default_permissions": (),
            },
        ),
    ]
