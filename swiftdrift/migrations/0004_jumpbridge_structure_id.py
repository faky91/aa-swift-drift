"""Add the in-game structure ID to jump bridges (corptools export format)."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("swiftdrift", "0003_wording_and_jumpbridge"),
    ]

    operations = [
        migrations.AddField(
            model_name="jumpbridge",
            name="structure_id",
            field=models.BigIntegerField(
                blank=True,
                null=True,
                verbose_name="Structure ID",
            ),
        ),
    ]
