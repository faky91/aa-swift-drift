"""Add the bookmark field: name of the in-game bookmark at the wormhole."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("swiftdrift", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="drifterwormhole",
            name="bookmark",
            field=models.CharField(
                blank=True,
                default="",
                max_length=100,
                verbose_name="Bookmark",
            ),
        ),
    ]
