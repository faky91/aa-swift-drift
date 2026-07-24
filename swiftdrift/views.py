"""
Views of the app.

Access control:
- basic_access:  view the list, search routes, use autocomplete
- edit_access:   report and edit wormholes, delete own entries
- manage_access: delete any entry
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import Permission, User
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from eve_sde.models import SolarSystem

from .forms import (
    KSPACE_MAX_ID,
    KSPACE_MIN_ID,
    JumpBridgeForm,
    RouteForm,
    WormholeForm,
)
from .models import DrifterWormhole, JumpBridge
from .routing import find_route

# Shared ESI client for this app (lazy, created once per process)
esi = EsiClientProvider(app_info_text="aa-swift-drift")

# The ESI scope needed to write autopilot waypoints into the game client
WAYPOINT_SCOPE = "esi-ui.write_waypoint.v1"

# Hard cap for the waypoint loop, protects against absurd inputs
MAX_WAYPOINTS = 50


@login_required
@permission_required("swiftdrift.basic_access")
def index(request):
    """Overview of all active drifter wormholes."""
    wormholes = (
        DrifterWormhole.active()
        .select_related("system__constellation__region", "created_by", "updated_by")
        .order_by("system__name")
    )
    context = {
        "wormholes": wormholes,
        "can_edit": request.user.has_perm("swiftdrift.edit_access"),
        "can_manage": request.user.has_perm("swiftdrift.manage_access"),
    }
    return render(request, "swiftdrift/index.html", context)


@login_required
@permission_required("swiftdrift.edit_access")
def add(request):
    """Report a new drifter wormhole."""
    if request.method == "POST":
        form = WormholeForm(request.POST)
        if form.is_valid():
            wormhole = DrifterWormhole(
                system=form.cleaned_data["system"],
                hive=form.cleaned_data["hive"],
                mass_status=form.cleaned_data["mass_status"],
                eol=form.cleaned_data["eol"],
                bookmark=form.cleaned_data["bookmark"],
                notes=form.cleaned_data["notes"],
                created_by=request.user,
                updated_by=request.user,
            )
            wormhole.save()
            messages.success(request, f"Wormhole in {wormhole.system.name} reported.")
            return redirect("swiftdrift:index")
    else:
        form = WormholeForm()

    context = {"form": form, "title": "Report wormhole"}
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
                "mass_status": wormhole.mass_status,
                "eol": wormhole.eol,
                "bookmark": wormhole.bookmark,
                "notes": wormhole.notes,
            }
        )

    context = {"form": form, "title": f"Edit wormhole: {wormhole.system.name}"}
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
    form = RouteForm(request.GET or None)

    # Only calculate when the form was submitted and is valid
    if request.GET and form.is_valid():
        result = find_route(
            start_id=form.cleaned_data["start_system"].id,
            dest_id=form.cleaned_data["dest_system"].id,
            use_drifters=form.cleaned_data["use_drifters"],
            use_bridges=form.cleaned_data["use_bridges"],
        )
        if result is None:
            messages.warning(request, "No route found.")
        else:
            # Number of jumps = steps without the starting point
            jumps = len(result) - 1

    context = {"form": form, "route": result, "jumps": jumps}
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
    context = {"form": form, "bridges": bridge_list}
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

    members = []
    for user in users:
        # Main character name from the Auth profile, if one is linked
        main_character = ""
        profile = getattr(user, "profile", None)
        if profile and getattr(profile, "main_character", None):
            main_character = profile.main_character.character_name

        members.append(
            {
                "user": user,
                "main_character": main_character,
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
    raw_ids = request.GET.get("system_ids", "")

    # Parse and validate: integers only, k-space range, sane count
    system_ids = []
    for part in raw_ids.split(","):
        part = part.strip()
        if not part.isdigit():
            continue
        system_id = int(part)
        if KSPACE_MIN_ID <= system_id < KSPACE_MAX_ID:
            system_ids.append(system_id)

    if not system_ids or len(system_ids) > MAX_WAYPOINTS:
        messages.error(request, "No valid route to send to the game client.")
        return redirect("swiftdrift:route")

    # First waypoint clears the existing route, the rest are appended
    clear_existing = True
    for system_id in system_ids:
        esi.client.User_Interface.post_ui_autopilot_waypoint(
            add_to_beginning=False,
            clear_other_waypoints=clear_existing,
            destination_id=system_id,
            token=token.valid_access_token(),
        ).result()
        clear_existing = False

    messages.success(
        request,
        f"Route with {len(system_ids)} waypoints sent to "
        f"{token.character_name}'s game client.",
    )
    return redirect("swiftdrift:route")


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
        names = list(
            SolarSystem.objects.filter(
                name__istartswith=query,
                id__gte=KSPACE_MIN_ID,
                id__lt=KSPACE_MAX_ID,
            )
            .order_by("name")
            .values_list("name", flat=True)[:10]
        )
    return JsonResponse({"results": names})
