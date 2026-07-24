"""
Alliance Auth hooks.

This file plugs the app into Auth:
- MenuItemHook: sidebar entry (only visible with basic_access)
- UrlHook:      mounts our URLs under /swift-drift/
"""

from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook

from . import urls


class SwiftDriftMenuItem(MenuItemHook):
    """Sidebar entry for the app."""

    def __init__(self):
        MenuItemHook.__init__(
            self,
            "Swift Drift",                 # display name in the menu
            "fa-solid fa-circle-notch",    # FontAwesome icon
            "swiftdrift:index",              # target URL (name from urls.py)
            navactive=["swiftdrift:"],       # mark the menu entry as active
        )

    def render(self, request):
        """Only show the menu entry if the user has the permission."""
        if request.user.has_perm("swiftdrift.basic_access"):
            return MenuItemHook.render(self, request)
        return ""


@hooks.register("menu_item_hook")
def register_menu():
    return SwiftDriftMenuItem()


@hooks.register("url_hook")
def register_urls():
    # All app URLs live under /swift-drift/
    return UrlHook(urls, "swiftdrift", r"^swift-drift/")
