"""Django admin: make wormholes visible in the admin backend (for superusers)."""

from django.contrib import admin

from .models import (
    DrifterWormhole,
    JumpBridge,
    WormholeReportLog,
    WormholeStatusReport,
)


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


@admin.register(WormholeReportLog)
class WormholeReportLogAdmin(admin.ModelAdmin):
    """
    Manual log administration.

    WARNING for admins: deleting log rows permanently reduces the
    affected users' leaderboard points and their report statistics on
    the team page. There is no undo and no recalculation, the log IS
    the counter. Deleting per user: filter/search for the user, select
    the rows (or use the action below), and confirm.
    """

    list_display = ("user", "hive", "created_at")
    search_fields = ("user__username",)
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    actions = ["delete_all_entries_of_selected_users"]

    @admin.action(
        description=(
            "Delete ALL log entries of the selected rows' users "
            "(PERMANENTLY resets their leaderboard points!)"
        )
    )
    def delete_all_entries_of_selected_users(self, request, queryset):
        user_ids = set(queryset.values_list("user_id", flat=True))
        deleted, _ = WormholeReportLog.objects.filter(
            user_id__in=user_ids
        ).delete()
        self.message_user(
            request,
            f"Deleted {deleted} log entries of {len(user_ids)} user(s). "
            "Their leaderboard points and team statistics are reset.",
        )
