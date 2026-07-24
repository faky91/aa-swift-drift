"""Django app configuration for aa-swiftdrift."""

from django.apps import AppConfig

from . import __version__


class SwiftDriftConfig(AppConfig):
    """Registers the app with Django."""

    name = "swiftdrift"
    label = "swiftdrift"
    verbose_name = f"Swift Drift v{__version__}"

    # Pin the auto field type so migrations stay identical regardless of
    # the DEFAULT_AUTO_FIELD setting of the host Auth project.
    # This matters for consistency between bare metal and Docker installs.
    default_auto_field = "django.db.models.AutoField"
