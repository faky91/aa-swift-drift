"""
Initial migration.

Creates the table for DrifterWormhole and registers the permission
carrier model "General" (which has no table of its own).
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("eve_sde", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Permission carrier model. managed=False means:
        # no table is created in the database.
        migrations.CreateModel(
            name="General",
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
            ],
            options={
                "managed": False,
                "default_permissions": (),
                "permissions": (
                    ("basic_access", "Swift Drift - Can view wormholes and find routes"),
                    ("edit_access", "Swift Drift - Can report and edit wormholes"),
                    ("manage_access", "Swift Drift - Can manage all wormhole entries"),
                ),
            },
        ),
        # The actual wormhole table
        migrations.CreateModel(
            name="DrifterWormhole",
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
                    "hive",
                    models.CharField(
                        choices=[
                            ("barbican", "Barbican"),
                            ("conflux", "Conflux"),
                            ("redoubt", "Redoubt"),
                            ("sentinel", "Sentinel"),
                            ("vidette", "Vidette"),
                        ],
                        max_length=16,
                        verbose_name="Hive",
                    ),
                ),
                (
                    "mass_status",
                    models.CharField(
                        choices=[
                            ("fresh", "Stable (fresh)"),
                            ("reduced", "Mass reduced"),
                            ("critical", "Mass critical"),
                        ],
                        default="fresh",
                        max_length=16,
                        verbose_name="Mass",
                    ),
                ),
                ("eol", models.BooleanField(default=False, verbose_name="End of Life")),
                ("eol_at", models.DateTimeField(blank=True, editable=False, null=True)),
                ("notes", models.TextField(blank=True, default="", verbose_name="Notes")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("expires_at", models.DateTimeField(db_index=True, editable=False)),
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
                    "updated_by",
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
                    "system",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="eve_sde.solarsystem",
                        verbose_name="System",
                    ),
                ),
            ],
            options={
                "verbose_name": "Drifter Wormhole",
                "verbose_name_plural": "Drifter Wormholes",
                "default_permissions": (),
            },
        ),
    ]
