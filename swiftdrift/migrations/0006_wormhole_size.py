"""Ship size limit for (normal) wormholes, using the in-game wording."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("swiftdrift", "0005_normal_wormholes_and_status_reports"),
    ]

    operations = [
        migrations.AddField(
            model_name="drifterwormhole",
            name="size",
            field=models.CharField(
                blank=True,
                choices=[
                    ("s", "Only the smallest ships can pass through this wormhole (S)"),
                    ("m", "Up to medium size ships can pass through this wormhole (M)"),
                    ("l", "Larger ships can pass through this wormhole (L)"),
                    ("xl", "Very large ships can pass through this wormhole (XL)"),
                ],
                default="",
                max_length=2,
                verbose_name="Size",
            ),
        ),
    ]
