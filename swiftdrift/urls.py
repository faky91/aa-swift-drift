"""URL definitions of the app. Included via the UrlHook in auth_hooks.py."""

from django.urls import path

from . import views

app_name = "swiftdrift"

urlpatterns = [
    # Overview of all active wormholes
    path("", views.index, name="index"),
    # Report / edit / delete (edit_access)
    path("add/", views.add, name="add"),
    path("<int:pk>/edit/", views.edit, name="edit"),
    path("<int:pk>/delete/", views.delete, name="delete"),
    # Route search (basic_access)
    path("route/", views.route, name="route"),
    # Fill the start system with the character's location (ESI scope)
    path("locate-me/", views.locate_me, name="locate_me"),
    # Send the route to the game client via ESI (basic_access + scope)
    path("set-destination/", views.set_destination, name="set_destination"),
    # Jump bridge management (edit_access)
    path("bridges/", views.bridges, name="bridges"),
    path("bridges/<int:pk>/delete/", views.bridge_delete, name="bridge_delete"),
    path("bridges/import/", views.bridges_import, name="bridges_import"),
    path("bridges/clear/", views.bridges_clear, name="bridges_clear"),
    # Leaderboard (basic_access)
    path("leaderboard/", views.leaderboard, name="leaderboard"),
    # One-click EOL toggle (edit_access)
    path("<int:pk>/toggle-eol/", views.toggle_eol, name="toggle_eol"),
    # Pilot status votes (basic_access)
    path("<int:pk>/vote/", views.vote, name="vote"),
    # Team overview (manage_access)
    path("team/", views.team, name="team"),
    # Autocomplete API for system names
    path("api/systems/", views.system_search, name="system_search"),
]
