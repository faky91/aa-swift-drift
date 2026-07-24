"""Wormhole type code from the bundled catalog; lifetime supports 4.5h."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("swiftdrift", "0006_wormhole_size"),
    ]

    operations = [
        migrations.AddField(
            model_name="drifterwormhole",
            name="wh_type_code",
            field=models.CharField(
                blank=True,
                default="",
                max_length=6,
                verbose_name="Wormhole type",
            ),
        ),
        migrations.AlterField(
            model_name="drifterwormhole",
            name="lifetime_hours",
            field=models.FloatField(
                blank=True,
                null=True,
                verbose_name="Lifetime (hours)",
            ),
        ),
    ]
