"""Normal wormholes (direct A-B connections) and pilot status reports."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("eve_sde", "0001_initial"),
        ("swiftdrift", "0004_jumpbridge_structure_id"),
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
                    ("normal", "Normal wormhole"),
                ],
                max_length=16,
                verbose_name="Wormhole",
            ),
        ),
        migrations.AddField(
            model_name="drifterwormhole",
            name="destination_system",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="eve_sde.solarsystem",
                verbose_name="Destination system",
            ),
        ),
        migrations.AddField(
            model_name="drifterwormhole",
            name="lifetime_hours",
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                verbose_name="Lifetime (hours)",
            ),
        ),
        migrations.CreateModel(
            name="WormholeStatusReport",
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
                ("is_up", models.BooleanField()),
                ("created_at", models.DateTimeField(auto_now=True, db_index=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "wormhole",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="status_reports",
                        to="swiftdrift.drifterwormhole",
                    ),
                ),
            ],
            options={"default_permissions": ()},
        ),
        migrations.AddConstraint(
            model_name="wormholestatusreport",
            constraint=models.UniqueConstraint(
                fields=("wormhole", "user"),
                name="swiftdrift_one_vote_per_user_and_wormhole",
            ),
        ),
    ]
