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
    # Jump bridge management (edit_access)
    path("bridges/", views.bridges, name="bridges"),
    path("bridges/<int:pk>/delete/", views.bridge_delete, name="bridge_delete"),
    # Team overview (manage_access)
    path("team/", views.team, name="team"),
    # Autocomplete API for system names
    path("api/systems/", views.system_search, name="system_search"),
]
