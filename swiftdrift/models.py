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
        # A regular (non-drifter) wormhole: a direct connection between
        # two known systems, like a bridge with an expiry date
        NORMAL = "normal", "Normal wormhole"

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
        verbose_name="Wormhole",
    )

    # Mass state
    mass_status = models.CharField(
        max_length=16,
        choices=MassStatus.choices,
        default=MassStatus.FRESH,
        verbose_name="Mass",
    )

    # End of life flag
    # Only for NORMAL wormholes: the system on the far side.
    # Drifter wormholes connect through their network instead.
    destination_system = models.ForeignKey(
        SolarSystem,
        on_delete=models.CASCADE,
        related_name="+",
        null=True,
        blank=True,
        verbose_name="Destination system",
    )

    # Optional lifetime override in hours (mainly for normal wormholes,
    # e.g. 24h or 48h holes). Empty = app default (16h).
    lifetime_hours = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Lifetime (hours)",
    )

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

    # Name of the in-game bookmark that marks the wormhole entrance.
    # Shown on the route page so pilots know what to warp to.
    bookmark = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Bookmark",
    )

    # Free text for anything else worth knowing
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

        # Creation time + lifetime (entry override or app default)
        lifetime = (
            self.lifetime_hours
            or app_settings.SWIFTDRIFT_DEFAULT_LIFETIME_HOURS
        )
        expires = created + datetime.timedelta(hours=lifetime)

        # EOL caps the remaining lifetime at X hours
        if self.eol and self.eol_at:
            eol_expires = self.eol_at + datetime.timedelta(
                hours=app_settings.SWIFTDRIFT_EOL_LIFETIME_HOURS
            )
            expires = min(expires, eol_expires)

        self.expires_at = expires
        super().save(*args, **kwargs)

    @property
    def freshness_percent(self) -> int:
        """
        Rough estimate (0-100) of how likely the wormhole still exists.

        Based on the remaining share of the entry's lifetime. This is an
        estimate: the hole may have spawned before it was reported, and
        EOL shortens the window (which lowers the value automatically,
        because expires_at is recalculated when EOL is set).
        """
        now = timezone.now()
        total = (self.expires_at - self.created_at).total_seconds()
        remaining = (self.expires_at - now).total_seconds()
        if total <= 0 or remaining <= 0:
            return 0
        return max(0, min(100, round(remaining / total * 100)))

    @property
    def is_expired(self) -> bool:
        """True if the entry has expired (safety net for display logic)."""
        return self.expires_at <= timezone.now()

    @classmethod
    def active(cls):
        """QuerySet of all currently valid wormholes."""
        return cls.objects.filter(expires_at__gt=timezone.now())

class JumpBridge(models.Model):
    """
    A player-owned Ansiblex jump bridge connection between two systems.

    One row represents the connection and is treated as bidirectional by
    the route planner (Ansiblex gates are usually deployed in pairs).
    Unlike wormholes, bridges are long-lived and do not expire.
    """

    from_system = models.ForeignKey(
        SolarSystem,
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name="From system",
    )
    to_system = models.ForeignKey(
        SolarSystem,
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name="To system",
    )

    # In-game structure ID; helps locating the Ansiblex in game and can
    # be used as an ESI waypoint target in a future version
    structure_id = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name="Structure ID",
    )

    # In-game structure name, e.g. "Y-2ANO --> KVN-36"
    structure_name = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Structure name",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="+",
    )

    class Meta:
        default_permissions = ()  # access is handled via General permissions
        verbose_name = "Jump Bridge"
        verbose_name_plural = "Jump Bridges"

    def __str__(self) -> str:
        return f"{self.from_system.name} <> {self.to_system.name}"


class WormholeStatusReport(models.Model):
    """
    A pilot's status vote for a wormhole: still open (up) or gone (down).

    Purely informational: the reports are DISPLAYED (e.g. "3 reports in
    the last hour: down") but never trigger automatic actions. One vote
    per user and wormhole; changing the vote refreshes the timestamp.
    Reports are deleted together with the wormhole (CASCADE), so the
    table stays small automatically.
    """

    wormhole = models.ForeignKey(
        DrifterWormhole,
        on_delete=models.CASCADE,
        related_name="status_reports",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="+",
    )
    # True = confirmed still open, False = reported gone/closed
    is_up = models.BooleanField()
    created_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["wormhole", "user"],
                name="swiftdrift_one_vote_per_user_and_wormhole",
            )
        ]

    def __str__(self) -> str:
        direction = "up" if self.is_up else "down"
        return f"{self.wormhole_id} {direction} by {self.user_id}"
