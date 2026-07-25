"""
Views of the app.

Access control:
- basic_access:  view the list, search routes, use autocomplete
- edit_access:   report and edit wormholes, delete own entries
- manage_access: delete any entry
"""

import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import Permission, User
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.urls import reverse

import requests
from esi.decorators import token_required

from eve_sde.models import SolarSystem

from .forms import (
    KSPACE_MAX_ID,
    KSPACE_MIN_ID,
    JumpBridgeForm,
    JumpBridgeImportForm,
    RouteForm,
    WormholeForm,
)
from .importer import parse_jump_bridges
from .models import (
    DrifterWormhole,
    JumpBridge,
    WormholeReportLog,
    WormholeStatusReport,
)
from . import wh_types
from .routing import find_route

# django-esi v9 removed the generated Swagger client (esi.clients), so we
# call the single endpoint we need directly via HTTP. Token management
# (SSO, refresh, the token_required decorator) still comes from django-esi.
ESI_WAYPOINT_URL = "https://esi.evetech.net/latest/ui/autopilot/waypoint/"

# The ESI scope needed to write autopilot waypoints into the game client
WAYPOINT_SCOPE = "esi-ui.write_waypoint.v1"



@login_required
@permission_required("swiftdrift.basic_access")
def index(request):
    """Overview of all active drifter wormholes."""
    wormholes = (
        DrifterWormhole.active()
        .select_related(
            "system__constellation__region",
            "destination_system",
            "created_by",
            "updated_by",
        )
        .annotate(
            up_votes=Count(
                "status_reports",
                filter=Q(status_reports__is_up=True),
            ),
            down_votes=Count(
                "status_reports",
                filter=Q(status_reports__is_up=False),
            ),
        )
        .order_by("system__name")
    )
    context = {
        "wormholes": wormholes,
        "can_edit": request.user.has_perm("swiftdrift.edit_access"),
        "can_manage": request.user.has_perm("swiftdrift.manage_access"),
    }
    return render(request, "swiftdrift/index.html", context)


@login_required
@permission_required("swiftdrift.basic_access")
def leaderboard(request):
    """
    Public leaderboard: 1 point per reported wormhole, counted from the
    permanent report log so expired entries still count.
    """
    now = timezone.now()
    cutoff_30 = now - datetime.timedelta(days=30)
    all_rows = list(
        WormholeReportLog.objects.values("user_id", "user__username")
        .annotate(
            points=Count("id"),
            last_30=Count("id", filter=Q(created_at__gte=cutoff_30)),
        )
        .order_by("-points", "user__username")
    )

    # Own rank, even outside the top 50
    own_rank = None
    own_points = 0
    for index, row in enumerate(all_rows):
        if row["user_id"] == request.user.id:
            own_rank = index + 1
            own_points = row["points"]
            break

    rows = all_rows[:50]

    # Main character names in one query
    user_ids = [row["user_id"] for row in rows]
    mains = {}
    for user in User.objects.filter(id__in=user_ids).select_related(
        "profile__main_character"
    ):
        profile = getattr(user, "profile", None)
        if profile and getattr(profile, "main_character", None):
            mains[user.id] = profile.main_character.character_name

    entries = [
        {
            "rank": index + 1,
            "user_id": row["user_id"],
            "username": row["user__username"],
            "main_character": mains.get(row["user_id"], ""),
            "points": row["points"],
            "last_30": row["last_30"],
        }
        for index, row in enumerate(rows)
    ]
    context = {
        "entries": entries,
        "own_rank": own_rank,
        "own_points": own_points,
        "own_in_top": any(e["user_id"] == request.user.id for e in entries),
    }
    return render(request, "swiftdrift/leaderboard.html", context)


def _wh_type_map() -> dict:
    """Catalog as a JS-friendly map for client-side auto-fill."""
    return {
        code: {
            "size": wh_types.size_for(code),
            "lifetime": wh_types.lifetime_for(code),
            "summary": wh_types.summary_for(code),
        }
        for code in wh_types.WH_TYPES
    }


@login_required
@permission_required("swiftdrift.edit_access")
def add(request):
    """Report a new drifter wormhole."""
    duplicate_of = None
    if request.method == "POST":
        form = WormholeForm(request.POST)
        if form.is_valid():
            # Duplicate guard: same system + same wormhole type already
            # active. The reporter sees a warning with a link to the
            # existing entry and can confirm to save anyway.
            existing = (
                DrifterWormhole.active()
                .filter(
                    system=form.cleaned_data["system"],
                    hive=form.cleaned_data["hive"],
                )
                .first()
            )
            if existing and not request.POST.get("confirm_duplicate"):
                duplicate_of = existing
                context = {
                    "form": form,
                    "title": "Report wormhole",
                    "duplicate_of": duplicate_of,
                    "wh_type_options": wh_types.choices(),
                    "wh_type_map": _wh_type_map(),
                }
                return render(request, "swiftdrift/form.html", context)

            wormhole = DrifterWormhole(
                system=form.cleaned_data["system"],
                hive=form.cleaned_data["hive"],
                destination_system=form.cleaned_data["destination_system"],
                wh_type_code=form.cleaned_data["wh_type"],
                size=form.cleaned_data["size"],
                lifetime_hours=form.cleaned_data["lifetime_hours"],
                mass_status=form.cleaned_data["mass_status"],
                eol=form.cleaned_data["eol"],
                bookmark=form.cleaned_data["bookmark"],
                notes=form.cleaned_data["notes"],
                created_by=request.user,
                updated_by=request.user,
            )
            wormhole.save()
            # Permanent log row: powers team stats and the leaderboard
            WormholeReportLog.objects.create(
                user=request.user, hive=wormhole.hive
            )
            messages.success(request, f"Wormhole in {wormhole.system.name} reported.")
            # "Report another": straight back to an empty form, because
            # scanners rarely report just one hole
            if request.POST.get("report_another"):
                return redirect("swiftdrift:add")
            return redirect("swiftdrift:index")
    else:
        form = WormholeForm()

    context = {
        "form": form,
        "title": "Report wormhole",
        "wh_type_options": wh_types.choices(),
        "wh_type_map": _wh_type_map(),
    }
    return render(request, "swiftdrift/form.html", context)


@login_required
@permission_required("swiftdrift.edit_access")
def edit(request, pk: int):
    """Edit an existing wormhole (update its state)."""
    wormhole = get_object_or_404(DrifterWormhole, pk=pk)

    if request.method == "POST":
        form = WormholeForm(request.POST)
        if form.is_valid():
            wormhole.system = form.cleaned_data["system"]
            wormhole.hive = form.cleaned_data["hive"]
            wormhole.destination_system = form.cleaned_data["destination_system"]
            wormhole.wh_type_code = form.cleaned_data["wh_type"]
            wormhole.size = form.cleaned_data["size"]
            wormhole.lifetime_hours = form.cleaned_data["lifetime_hours"]
            wormhole.mass_status = form.cleaned_data["mass_status"]
            wormhole.eol = form.cleaned_data["eol"]
            wormhole.bookmark = form.cleaned_data["bookmark"]
            wormhole.notes = form.cleaned_data["notes"]
            wormhole.updated_by = request.user
            wormhole.save()
            messages.success(request, f"Wormhole in {wormhole.system.name} updated.")
            return redirect("swiftdrift:index")
    else:
        # Pre-fill the form with the current values
        form = WormholeForm(
            initial={
                "system_name": wormhole.system.name,
                "hive": wormhole.hive,
                "destination_name": (
                    wormhole.destination_system.name
                    if wormhole.destination_system
                    else ""
                ),
                "wh_type": wormhole.wh_type_code,
                "size": wormhole.size,
                "lifetime_hours": wormhole.lifetime_hours,
                "mass_status": wormhole.mass_status,
                "eol": wormhole.eol,
                "bookmark": wormhole.bookmark,
                "notes": wormhole.notes,
            }
        )

    context = {
        "form": form,
        "title": f"Edit wormhole: {wormhole.system.name}",
        "wh_type_options": wh_types.choices(),
        "wh_type_map": _wh_type_map(),
    }
    return render(request, "swiftdrift/form.html", context)


@login_required
@permission_required("swiftdrift.edit_access")
def delete(request, pk: int):
    """
    Delete a wormhole.
    Editors may only delete their own entries, admins may delete any.
    """
    wormhole = get_object_or_404(DrifterWormhole, pk=pk)

    is_owner = wormhole.created_by_id == request.user.id
    is_manager = request.user.has_perm("swiftdrift.manage_access")
    if not (is_owner or is_manager):
        messages.error(request, "You may only delete your own entries.")
        return redirect("swiftdrift:index")

    if request.method == "POST":
        name = wormhole.system.name
        wormhole.delete()
        messages.success(request, f"Wormhole in {name} deleted.")
    return redirect("swiftdrift:index")


@login_required
@permission_required("swiftdrift.basic_access")
def route(request):
    """Route search: start to destination, optionally via drifter shortcuts."""
    result = None
    jumps = None
    avoid_ids = []
    gate_only_jumps = None
    saved_jumps = None
    form = RouteForm(request.GET or None)

    # Only calculate when the form was submitted and is valid
    if request.GET and form.is_valid():
        # "Find alternative route": wormhole ids the user distrusts,
        # accumulated across repeated clicks
        avoid_ids = [
            int(part)
            for part in request.GET.get("avoid", "").split(",")
            if part.strip().isdigit()
        ]

        result = find_route(
            start_id=form.cleaned_data["start_system"].id,
            dest_id=form.cleaned_data["dest_system"].id,
            use_drifters=form.cleaned_data["use_drifters"],
            use_bridges=form.cleaned_data["use_bridges"],
            use_normal=form.cleaned_data["use_normal_wh"],
            exclude_wormhole_ids=avoid_ids,
        )
        if result is None:
            messages.warning(request, "No route found.")
        else:
            # Number of jumps = steps without the starting point
            jumps = len(result) - 1

            # Gate-only comparison: shows every user what the shortcuts
            # save. Second Dijkstra on the cached graph, cheap.
            if (
                form.cleaned_data["use_drifters"]
                or form.cleaned_data["use_normal_wh"]
                or form.cleaned_data["use_bridges"]
            ):
                gate_only = find_route(
                    start_id=form.cleaned_data["start_system"].id,
                    dest_id=form.cleaned_data["dest_system"].id,
                    use_drifters=False,
                    use_bridges=False,
                    use_normal=False,
                )
                gate_only_jumps = len(gate_only) - 1 if gate_only else None
                if gate_only_jumps is not None:
                    saved_jumps = gate_only_jumps - jumps

    # Target for "set destination": the system that CONTAINS the (first)
    # wormhole entry on the route; the pilot flies there via gates and
    # continues manually. Routes without a wormhole leg target the final
    # system instead.
    destination_target = None
    if result:
        for step in result:
            if step.get("enter_hive"):
                destination_target = step["system"]
                break
        if destination_target is None:
            destination_target = result[-1]["system"]

    # Wormhole entries used by this route: shown with their status and
    # offered for exclusion via the "find alternative route" button
    used_wormhole_ids = set()
    if result:
        for step in result:
            for key in ("enter_status", "exit_status"):
                if step.get(key):
                    used_wormhole_ids.add(step[key]["id"])

    # Shareable plain-text version of the route for Discord/in-game chat
    share_text = ""
    if result:
        lines = [
            f"Route {result[0]['system'].name} -> "
            f"{result[-1]['system'].name} ({jumps} jumps)"
        ]
        for number, step in enumerate(result):
            if step["action"] == "gate":
                action = "take gate"
            elif step["action"] == "bridge":
                action = f"jump bridge {step['bridge_label']}"
            elif step["action"] == "drifter":
                hive = (step.get("enter_hive") or "wormhole").capitalize()
                bookmark = step.get("enter_bookmark") or "bookmark unknown"
                action = f"ENTER {hive} ({bookmark})"
            else:
                action = "destination"
            lines.append(f"{number}. {step['system'].name} - {action}")
        share_text = "\n".join(lines)

    context = {
        "form": form,
        "route": result,
        "jumps": jumps,
        "gate_only_jumps": gate_only_jumps,
        "saved_jumps": saved_jumps,
        "share_text": share_text,
        "destination_target": destination_target,
        "avoided_count": len(avoid_ids),
        # Next avoid value = already avoided + this route's wormholes
        "avoid_next": ",".join(
            str(pk) for pk in sorted(set(avoid_ids) | used_wormhole_ids)
        ),
        "route_uses_wormholes": bool(used_wormhole_ids),
    }
    return render(request, "swiftdrift/route.html", context)


@login_required
@permission_required("swiftdrift.edit_access")
def bridges(request):
    """List all jump bridges and add new ones (editors)."""
    if request.method == "POST":
        form = JumpBridgeForm(request.POST)
        if form.is_valid():
            bridge = JumpBridge(
                from_system=form.cleaned_data["from_system"],
                to_system=form.cleaned_data["to_system"],
                structure_name=form.cleaned_data["structure_name"],
                created_by=request.user,
            )
            bridge.save()
            messages.success(
                request,
                f"Jump bridge {bridge.from_system.name} <> "
                f"{bridge.to_system.name} added.",
            )
            return redirect("swiftdrift:bridges")
    else:
        form = JumpBridgeForm()

    bridge_list = JumpBridge.objects.select_related(
        "from_system", "to_system", "created_by"
    ).order_by("from_system__name")
    context = {
        "form": form,
        "import_form": JumpBridgeImportForm(),
        "bridges": bridge_list,
        "can_manage": request.user.has_perm("swiftdrift.manage_access"),
    }
    return render(request, "swiftdrift/bridges.html", context)


@login_required
@permission_required("swiftdrift.edit_access")
def bridge_delete(request, pk: int):
    """
    Delete a jump bridge.
    Editors may only delete their own entries, admins may delete any.
    """
    bridge = get_object_or_404(JumpBridge, pk=pk)

    is_owner = bridge.created_by_id == request.user.id
    is_manager = request.user.has_perm("swiftdrift.manage_access")
    if not (is_owner or is_manager):
        messages.error(request, "You may only delete your own entries.")
        return redirect("swiftdrift:bridges")

    if request.method == "POST":
        name = str(bridge)
        bridge.delete()
        messages.success(request, f"Jump bridge {name} deleted.")
    return redirect("swiftdrift:bridges")


@login_required
@permission_required("swiftdrift.edit_access")
def bridges_import(request):
    """
    Bulk import of jump bridges from a pasted list.
    "Replace existing" wipes the table first and requires manage_access,
    because it also removes bridges added by other editors.
    """
    if request.method != "POST":
        return redirect("swiftdrift:bridges")

    form = JumpBridgeImportForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Import form was invalid.")
        return redirect("swiftdrift:bridges")

    replace = form.cleaned_data["replace_existing"]
    if replace and not request.user.has_perm("swiftdrift.manage_access"):
        messages.error(
            request, "Replacing all bridges requires admin access."
        )
        return redirect("swiftdrift:bridges")

    entries, errors = parse_jump_bridges(form.cleaned_data["import_text"])

    if not entries and errors:
        # Nothing usable: report and change nothing
        for error in errors[:10]:
            messages.error(request, error)
        return redirect("swiftdrift:bridges")

    deleted_count = 0
    if replace:
        deleted_count, _ = JumpBridge.objects.all().delete()

    # Skip pairs that already exist (in either direction)
    existing = set()
    for a, b in JumpBridge.objects.values_list("from_system_id", "to_system_id"):
        existing.add(tuple(sorted((a, b))))

    created = 0
    skipped = 0
    for entry in entries:
        pair = tuple(sorted((entry["from_system"].id, entry["to_system"].id)))
        if pair in existing:
            skipped += 1
            continue
        JumpBridge.objects.create(
            from_system=entry["from_system"],
            to_system=entry["to_system"],
            structure_name=entry["structure_name"],
            structure_id=entry["structure_id"],
            created_by=request.user,
        )
        existing.add(pair)
        created += 1

    summary = f"Import finished: {created} bridges created"
    if skipped:
        summary += f", {skipped} duplicates skipped"
    if replace:
        summary += f", {deleted_count} old entries removed first"
    messages.success(request, summary + ".")

    # Show up to 10 unparsed lines so the user can fix their list
    for error in errors[:10]:
        messages.warning(request, error)
    if len(errors) > 10:
        messages.warning(request, f"...and {len(errors) - 10} more unparsed lines.")

    return redirect("swiftdrift:bridges")


@login_required
@permission_required("swiftdrift.manage_access")
def bridges_clear(request):
    """Delete ALL jump bridges (admins only, POST only)."""
    if request.method == "POST":
        deleted_count, _ = JumpBridge.objects.all().delete()
        messages.success(request, f"All {deleted_count} jump bridges deleted.")
    return redirect("swiftdrift:bridges")


@login_required
@permission_required("swiftdrift.edit_access")
def toggle_eol(request, pk: int):
    """One-click EOL toggle from the overview (editors)."""
    if request.method != "POST":
        return redirect("swiftdrift:index")
    wormhole = get_object_or_404(DrifterWormhole, pk=pk)
    wormhole.eol = not wormhole.eol
    wormhole.updated_by = request.user
    wormhole.save()
    state = "set" if wormhole.eol else "cleared"
    messages.success(
        request, f"EOL {state} for {wormhole.system.name}."
    )
    next_url = request.POST.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}
    ):
        return redirect(next_url)
    return redirect("swiftdrift:index")


@login_required
@permission_required("swiftdrift.basic_access")
def vote(request, pk: int):
    """
    Pilot status vote for a wormhole: up = confirmed open, down =
    reported gone. One changeable vote per user and wormhole. Purely
    informational, never triggers automatic actions.
    """
    if request.method != "POST":
        return redirect("swiftdrift:index")

    wormhole = get_object_or_404(DrifterWormhole, pk=pk)
    direction = request.POST.get("direction")
    if direction not in ("up", "down"):
        return redirect("swiftdrift:index")

    WormholeStatusReport.objects.update_or_create(
        wormhole=wormhole,
        user=request.user,
        defaults={"is_up": direction == "up"},
    )
    label = "still open" if direction == "up" else "gone"
    messages.success(
        request,
        f"Noted: {wormhole.system.name} reported as {label}. "
        "Thanks for the intel.",
    )

    # Return to the page the vote came from (overview or route)
    next_url = request.POST.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}
    ):
        return redirect(next_url)
    return redirect("swiftdrift:index")


@login_required
@permission_required("swiftdrift.manage_access")
def team(request):
    """
    Team overview for admins: who has editor or admin access, and
    through which Auth groups the access is granted.

    Access itself is managed through groups in Alliance Auth (Group
    Management or the Django admin), NOT here. This page is read-only
    on purpose so there is exactly one place where permissions change.
    """
    # The two write-level permissions of this app
    edit_perm = Permission.objects.get(
        codename="edit_access", content_type__app_label="swiftdrift"
    )
    manage_perm = Permission.objects.get(
        codename="manage_access", content_type__app_label="swiftdrift"
    )

    # Everyone who holds one of them, via a group or assigned directly
    users = (
        User.objects.filter(
            Q(groups__permissions__in=[edit_perm, manage_perm])
            | Q(user_permissions__in=[edit_perm, manage_perm])
        )
        .distinct()
        .order_by("username")
    )

    # Report counts per user from the permanent log (the wormhole
    # entries themselves are deleted after expiry). One query for all
    # windows via conditional aggregation.
    now = timezone.now()
    windows = {
        "d30": now - datetime.timedelta(days=30),
        "d90": now - datetime.timedelta(days=90),
        "d180": now - datetime.timedelta(days=180),
        "d365": now - datetime.timedelta(days=365),
    }
    counts = {
        row["user_id"]: row
        for row in WormholeReportLog.objects.filter(user__in=users)
        .values("user_id")
        .annotate(
            d30=Count("id", filter=Q(created_at__gte=windows["d30"])),
            d90=Count("id", filter=Q(created_at__gte=windows["d90"])),
            d180=Count("id", filter=Q(created_at__gte=windows["d180"])),
            d365=Count("id", filter=Q(created_at__gte=windows["d365"])),
            total=Count("id"),
        )
    }

    members = []
    for user in users:
        # Main character name from the Auth profile, if one is linked
        main_character = ""
        profile = getattr(user, "profile", None)
        if profile and getattr(profile, "main_character", None):
            main_character = profile.main_character.character_name

        user_counts = counts.get(user.id, {})
        members.append(
            {
                "user": user,
                "main_character": main_character,
                "reports_30": user_counts.get("d30", 0),
                "reports_90": user_counts.get("d90", 0),
                "reports_180": user_counts.get("d180", 0),
                "reports_365": user_counts.get("d365", 0),
                "reports_total": user_counts.get("total", 0),
                "is_editor": user.has_perm("swiftdrift.edit_access"),
                "is_admin": user.has_perm("swiftdrift.manage_access"),
                # Groups of this user that grant one of the permissions
                "via_groups": user.groups.filter(
                    permissions__in=[edit_perm, manage_perm]
                ).distinct(),
            }
        )

    context = {"members": members}
    return render(request, "swiftdrift/team.html", context)


def _route_url_with_params(request):
    """
    URL of the route page including the original search parameters.

    The set-destination form passes the route search (start, destination,
    checkboxes) along with the target system id. django-esi preserves the
    full query string through the SSO character selection, so after the
    ESI call we can send the user back to their calculated route instead
    of an empty search form.
    """
    params = request.GET.copy()
    params.pop("system_id", None)
    url = reverse("swiftdrift:route")
    query = params.urlencode()
    return f"{url}?{query}" if query else url


@login_required
@permission_required("swiftdrift.basic_access")
@token_required(scopes=WAYPOINT_SCOPE)
def set_destination(request, token):
    """
    Push the calculated route into the game client as autopilot waypoints.

    Uses the ESI scope esi-ui.write_waypoint.v1. On the first call,
    django-esi redirects the user through EVE SSO to authorize the scope
    for one of their characters; the token is then reused. Because of
    that redirect, the route arrives as a GET parameter (POST bodies do
    not survive the SSO round trip).

    Note: the in-game autopilot only understands stargate routes. This
    sets one waypoint per system of our route; wormhole and jump bridge
    legs are flown manually by the pilot.
    """
    raw_id = request.GET.get("system_id", "").strip()
    if not raw_id.isdigit() or not (KSPACE_MIN_ID <= int(raw_id) < KSPACE_MAX_ID):
        messages.error(request, "No valid destination system.")
        return redirect(_route_url_with_params(request))
    system_id = int(raw_id)

    system = SolarSystem.objects.filter(id=system_id).first()
    system_name = system.name if system else str(system_id)

    headers = {
        "Authorization": f"Bearer {token.valid_access_token()}",
        "User-Agent": "aa-swift-drift (https://github.com/faky91/aa-swift-drift)",
    }
    try:
        response = requests.post(
            ESI_WAYPOINT_URL,
            params={
                "add_to_beginning": "false",
                "clear_other_waypoints": "true",
                "destination_id": system_id,
            },
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        messages.error(request, f"ESI request failed: {error}")
        return redirect(_route_url_with_params(request))

    messages.success(
        request,
        f"Destination set to {system_name} in "
        f"{token.character_name}'s game client.",
    )
    return redirect(_route_url_with_params(request))


@login_required
@permission_required("swiftdrift.basic_access")
def system_search(request):
    """
    JSON endpoint for the system name autocomplete.
    Example: /swiftdrift/api/systems/?q=jit  ->  ["Jita", ...]
    """
    query = request.GET.get("q", "").strip()
    names = []
    if len(query) >= 2:  # only search from 2 characters onwards
        # K-space and J-space (route search and normal-wormhole
        # destinations may target wormhole systems like J123456)
        names = list(
            SolarSystem.objects.filter(name__istartswith=query)
            .order_by("name")
            .values_list("name", flat=True)[:10]
        )
    return JsonResponse({"results": names})
