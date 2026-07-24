"""Django admin: make wormholes visible in the admin backend (for superusers)."""

from django.contrib import admin

from .models import DrifterWormhole


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
