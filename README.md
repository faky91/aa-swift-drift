# aa-swift-drift

Swift Drift - a Drifter Wormhole Tracker for [Alliance Auth](https://gitlab.com/allianceauth/allianceauth).

Allows a group of users with the right permissions to report and manage
drifter wormholes (Barbican, Conflux, Redoubt, Sentinel, Vidette) in
k-space systems. View-only users can calculate routes between two
systems, using active drifter wormholes as shortcuts.

## Features

- Three roles via Auth permissions: view only, edit, admin
- Report wormholes with system autocomplete, hive type, mass status, EOL flag and notes
- Automatic expiry of entries (default: 16h, capped at 4h after EOL) via Celery task
- Route search from start to destination with drifter shortcuts (Dijkstra over stargates + active wormholes)
- Bootstrap 5, inherits the active theme of the Auth installation

## Requirements

- Alliance Auth >= 4 (Bootstrap 5)
- [django-eveonline-sde](https://github.com/Solar-Helix-Independent-Transport/django-eveonline-sde) (eve_sde)
- django-esi >= 9

If you are already running an app that uses eve_sde (for example
allianceauth-corptools), eve_sde is already installed and loaded on
your system and no extra setup is needed for it.

## Installation: bare metal

Run all commands inside the venv of the Auth installation
(e.g. as user `allianceserver`):

```bash
# 1. Activate the venv
source /home/allianceserver/venv/auth/bin/activate

# 2. Install the app (from a git repo, or from PyPI if published)
pip install git+https://github.com/faky91/aa-swift-drift.git@v0.8.1
# alternatively from a local checkout:
# pip install /path/to/aa-swift-drift
```

Then in `myauth/settings/local.py`:

```python
# Register the app
INSTALLED_APPS += [
    "swiftdrift",
]

# Only needed if no other app has installed eve_sde yet:
# modeltranslation must be FIRST in INSTALLED_APPS, then add eve_sde.
# INSTALLED_APPS.insert(0, "modeltranslation")
# INSTALLED_APPS += ["eve_sde"]

# Periodic task: delete expired wormholes every 5 minutes
CELERYBEAT_SCHEDULE["swiftdrift_delete_expired"] = {
    "task": "swiftdrift.tasks.delete_expired_wormholes",
    "schedule": crontab(minute="*/5"),
}

# Recommended (from the eve_sde README): daily check for SDE updates.
# Skip this if another eve_sde-based app already configured it.
if "eve_sde" in INSTALLED_APPS:
    CELERYBEAT_SCHEDULE["EVE SDE :: Check for SDE Updates"] = {
        "task": "eve_sde.tasks.check_for_sde_updates",
        "schedule": crontab(minute="0", hour="12"),
    }
```

Note: `from celery.schedules import crontab` is already at the top of the
standard `local.py`; add it if it is missing.

Afterwards:

```bash
# Create the database tables
python /home/allianceserver/myauth/manage.py migrate

# Collect static files
python /home/allianceserver/myauth/manage.py collectstatic --noinput

# Load the SDE (skip if another app already loaded it; runs via Celery)
python /home/allianceserver/myauth/manage.py esde_load_sde

# Restart Auth
supervisorctl restart myauth:
```

## Installation: Docker

In the Docker variant of Auth, the app is installed via the requirements
of the Auth image. Add to `conf/requirements.txt`:

```
aa-swift-drift @ git+https://github.com/faky91/aa-swift-drift.git@v0.8.1
```

The `local.py` entries are identical to the bare metal installation
(see above; in the Docker setup the file lives at `conf/local.py`).

Then rebuild the image and run the migrations:

```bash
docker compose build
docker compose up -d
docker compose exec allianceauth_gunicorn bash

# inside the container:
auth migrate
auth collectstatic --noinput
# Skip the next line if another app already loaded the SDE
auth esde_load_sde
```

The Celery Beat entry from `local.py` is picked up automatically by the
beat container; nothing else to do there.

## ESI scope for "Set destination in game"

The route page can push the calculated route into the game client as
autopilot waypoints. This uses the ESI scope
`esi-ui.write_waypoint.v1`, which must be added to the EVE application
of your Auth installation at https://developers.eveonline.com
(the same application whose client id/secret are configured in Auth).
Without the scope, the SSO authorization for the button will fail.
No changes to local.py are required; django-esi requests the scope
on first use.

## Permissions

The app ships three permissions which are assigned to groups via
**Admin > Groups** in Auth. All permission names are prefixed with
"Swift Drift" so they are easy to find in the long permission list:

| Permission | Shown as | Effect |
|---|---|---|
| `swiftdrift.basic_access` | Swift Drift - Can view wormholes and find routes | View only |
| `swiftdrift.edit_access` | Swift Drift - Can report and edit wormholes | Report, edit, delete own entries |
| `swiftdrift.manage_access` | Swift Drift - Can manage all wormhole entries | Additionally delete entries of other users |

Tip: type "Swift Drift" into the permission filter box in the Django
admin to see only these three.

Recommendation: create three groups (e.g. "Swift Drift Viewer",
"Swift Drift Editor", "Swift Drift Admin") and stack the permissions
accordingly. Editors need `basic_access` AND `edit_access`,
admins need all three.

## Settings (optional, local.py)

| Setting | Default | Description |
|---|---|---|
| `SWIFTDRIFT_DEFAULT_LIFETIME_HOURS` | 16 | Maximum lifetime of an entry from creation |
| `SWIFTDRIFT_EOL_LIFETIME_HOURS` | 4 | Remaining lifetime after the EOL flag is set |
| `SWIFTDRIFT_ROUTE_WH_WEIGHT` | 2 | Cost of a drifter jump in the route planner (in gates) |
| `SWIFTDRIFT_GRAPH_CACHE_SECONDS` | 86400 | Cache duration of the stargate graph |

## Project structure

```
aa-swift-drift/
├── pyproject.toml              Package definition and dependencies
├── README.md
└── swiftdrift/
    ├── __init__.py             Version number
    ├── apps.py                 Django app configuration
    ├── app_settings.py         Settings with defaults
    ├── auth_hooks.py           Auth integration (menu + URLs)
    ├── models.py               General (permissions) and DrifterWormhole
    ├── forms.py                Forms (report, route)
    ├── views.py                Pages and autocomplete API
    ├── urls.py                 URL routing
    ├── routing.py              Dijkstra route calculation
    ├── tasks.py                Celery task for expiry
    ├── admin.py                Django admin
    ├── migrations/
    │   └── 0001_initial.py     Database schema
    ├── static/swiftdrift/img/
    │   └── happydrifter.png    App mascot shown in the footer
    └── templates/swiftdrift/
        ├── base.html           Base layout + autocomplete script
        ├── index.html          Overview
        ├── form.html           Report/edit
        └── route.html          Route search
```

## Upgrading from 0.1.x (eveuniverse-based)

Version 0.2.0 switched the SDE backend from django-eveuniverse to
django-eveonline-sde. The wormhole table references the solar system
model of the backend, so the app tables must be rebuilt once. All
wormhole entries are short-lived anyway, so nothing of value is lost:

```bash
# BEFORE upgrading the package: roll back the app tables
auth migrate swiftdrift zero

# then update the pin in requirements to v0.2.0, rebuild, and:
auth migrate
```

## License

MIT
