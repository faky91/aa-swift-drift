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

from .forms import KSPACE_MAX_ID, KSPACE_MIN_ID, RouteForm, WormholeForm
from .models import DrifterWormhole
from .routing import find_route


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
        )
        if result is None:
            messages.warning(request, "No route found.")
        else:
            # Number of jumps = steps without the starting point
            jumps = len(result) - 1

    context = {"form": form, "route": result, "jumps": jumps}
    return render(request, "swiftdrift/route.html", context)


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
