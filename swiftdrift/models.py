"""
Data models of the app.

There are two models:

1. General
   An "empty" model without a database table. It only carries the three
   app permissions (view only / edit / admin). This is the standard
   pattern used by Alliance Auth apps.

2. DrifterWormhole
   A reported drifter wormhole in a k-space system, including hive type,
   status flags, timestamps and an automatically calculated expiry date.
"""

import datetime

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from eve_sde.models import SolarSystem

from . import app_settings


class General(models.Model):
    """Permission carrier model. Does NOT create a database table."""

    class Meta:
        managed = False  # do not create a database table
        default_permissions = ()  # no default add/change/delete/view perms
        permissions = (
            # View only: may see the app and search for routes
            ("basic_access", "Swift Drift - Can view wormholes and find routes"),
            # Edit: may report and edit wormholes
            ("edit_access", "Swift Drift - Can report and edit wormholes"),
            # Admin: may delete entries of other users and manage everything
            ("manage_access", "Swift Drift - Can manage all wormhole entries"),
        )


class DrifterWormhole(models.Model):
    """A reported drifter wormhole in a specific system."""

    # ------------------------------------------------------------------
    # Choice lists
    # ------------------------------------------------------------------

    class Hive(models.TextChoices):
        """The five drifter hives. The first value is stored in the DB."""

        BARBICAN = "barbican", "Barbican"
        CONFLUX = "conflux", "Conflux"
        REDOUBT = "redoubt", "Redoubt"
        SENTINEL = "sentinel", "Sentinel"
        VIDETTE = "vidette", "Vidette"

    class MassStatus(models.TextChoices):
        """Mass state of the wormhole."""

        FRESH = "fresh", "Stable (fresh)"
        REDUCED = "reduced", "Mass reduced"
        CRITICAL = "critical", "Mass critical"

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------

    # The k-space system where the wormhole was found
    system = models.ForeignKey(
        SolarSystem,
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name="System",
    )

    # Which drifter hive (Barbican, Conflux, ...)
    hive = models.CharField(
        max_length=16,
        choices=Hive.choices,
        verbose_name="Hive",
    )

    # Mass state
    mass_status = models.CharField(
        max_length=16,
        choices=MassStatus.choices,
        default=MassStatus.FRESH,
        verbose_name="Mass",
    )

    # End of life flag
    eol = models.BooleanField(
        default=False,
        verbose_name="End of Life",
    )

    # Timestamp when EOL was set (used for the expiry calculation)
    eol_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
    )

    # Free text, e.g. bookmark name or location inside the system
    notes = models.TextField(
        blank=True,
        default="",
        verbose_name="Notes",
    )

    # Timestamps and users (maintained automatically)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="+",
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="+",
    )

    # Expiry timestamp. Calculated in save() and evaluated by the Celery
    # task that deletes expired entries.
    expires_at = models.DateTimeField(db_index=True, editable=False)

    class Meta:
        default_permissions = ()  # access is handled via General permissions
        verbose_name = "Drifter Wormhole"
        verbose_name_plural = "Drifter Wormholes"

    # ------------------------------------------------------------------
    # Logic
    # ------------------------------------------------------------------

    def __str__(self) -> str:
        return f"{self.system.name} - {self.get_hive_display()}"

    def save(self, *args, **kwargs):
        """Calculate the expiry date before saving."""
        now = timezone.now()

        # Creation time: for new objects created_at is not set yet
        # (auto_now_add only kicks in on INSERT)
        created = self.created_at or now

        # Remember the moment the EOL flag is set for the first time
        if self.eol and self.eol_at is None:
            self.eol_at = now
        if not self.eol:
            self.eol_at = None

        # Default: creation time + maximum lifetime
        expires = created + datetime.timedelta(
            hours=app_settings.SWIFTDRIFT_DEFAULT_LIFETIME_HOURS
        )

        # EOL caps the remaining lifetime at X hours
        if self.eol and self.eol_at:
            eol_expires = self.eol_at + datetime.timedelta(
                hours=app_settings.SWIFTDRIFT_EOL_LIFETIME_HOURS
            )
            expires = min(expires, eol_expires)

        self.expires_at = expires
        super().save(*args, **kwargs)

    @property
    def is_expired(self) -> bool:
        """True if the entry has expired (safety net for display logic)."""
        return self.expires_at <= timezone.now()

    @classmethod
    def active(cls):
        """QuerySet of all currently valid wormholes."""
        return cls.objects.filter(expires_at__gt=timezone.now())
