"""Django admin: make wormholes visible in the admin backend (for superusers)."""

from django.contrib import admin

from .models import DrifterWormhole, JumpBridge, WormholeStatusReport


@admin.register(DrifterWormhole)
class DrifterWormholeAdmin(admin.ModelAdmin):
    list_display = (
        "system",
        "hive",
        "mass_status",
        "eol",
        "created_by",
        "created_at",
        "expires_at",
    )
    list_filter = ("hive", "mass_status", "eol")
    search_fields = ("system__name",)
    ordering = ("-created_at",)


@admin.register(JumpBridge)
class JumpBridgeAdmin(admin.ModelAdmin):
    list_display = ("from_system", "to_system", "structure_name", "created_by", "created_at")
    search_fields = ("from_system__name", "to_system__name", "structure_name")
    ordering = ("from_system__name",)


@admin.register(WormholeStatusReport)
class WormholeStatusReportAdmin(admin.ModelAdmin):
    list_display = ("wormhole", "user", "is_up", "created_at")
    list_filter = ("is_up",)
