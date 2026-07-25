"""
Forms of the app.

Systems are entered via a text field with autocomplete and resolved
server-side against the SDE database (eve_sde). This is more robust than
a dropdown with ~5000 entries.
"""

from django import forms

from eve_sde.models import SolarSystem

from . import wh_types
from .models import DrifterWormhole

# K-space systems have IDs from 30000000 to 30999999.
# J-space (wormhole space) starts at 31000000 and is excluded because
# drifter wormholes are only tracked in k-space.
KSPACE_MIN_ID = 30000000
KSPACE_MAX_ID = 31000000


def resolve_kspace_system(name: str) -> SolarSystem:
    """
    Resolve a system name to a SolarSystem object.
    Raises ValidationError if the system does not exist.
    """
    try:
        return SolarSystem.objects.get(
            name__iexact=name.strip(),
            id__gte=KSPACE_MIN_ID,
            id__lt=KSPACE_MAX_ID,
        )
    except SolarSystem.DoesNotExist:
        raise forms.ValidationError(
            f"System '{name}' not found. Please enter a valid "
            "k-space system name."
        )


def resolve_any_system(name: str) -> SolarSystem:
    """
    Resolve a system name to a SolarSystem object, including J-space
    wormhole systems (J-numbers, Thera). Used for the route search and
    the destination of normal wormholes; the reported side of an entry
    stays k-space, since that is where this tracker operates.
    """
    try:
        return SolarSystem.objects.get(name__iexact=name.strip())
    except SolarSystem.DoesNotExist:
        raise forms.ValidationError(
            f"System '{name}' not found. Please enter a valid system name."
        )


class WormholeForm(forms.Form):
    """Form for reporting and editing a drifter wormhole."""

    system_name = forms.CharField(
        label="System",
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g. Jita",
                "autocomplete": "off",
                # Custom attribute that activates our autocomplete script
                "data-system-autocomplete": "1",
            }
        ),
    )
    hive = forms.ChoiceField(
        label="Wormhole",
        choices=DrifterWormhole.Hive.choices,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    wh_type = forms.CharField(
        label="Wormhole type",
        required=False,
        max_length=6,
        help_text="Normal wormholes only: the in-game type code. "
                  "Known codes auto-fill size and lifetime.",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g. B274 or K162",
                "autocomplete": "off",
                "list": "wh-type-list",
            }
        ),
    )
    destination_name = forms.CharField(
        label="Destination system",
        required=False,
        max_length=100,
        help_text="Normal wormholes only: the system on the far side.",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g. Amarr (normal wormholes only)",
                "autocomplete": "off",
                "data-system-autocomplete": "1",
            }
        ),
    )
    size = forms.ChoiceField(
        label="Size",
        required=False,
        choices=[("", "Unknown")] + DrifterWormhole.Size.choices,
        help_text="Normal wormholes only: the in-game ship size limit.",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    lifetime_hours = forms.FloatField(
        label="Lifetime (hours)",
        required=False,
        min_value=0.5,
        max_value=72,
        help_text="Optional, defaults to 16h. Mainly for normal wormholes.",
        widget=forms.NumberInput(
            attrs={"class": "form-control", "placeholder": "16"}
        ),
    )
    mass_status = forms.ChoiceField(
        label="Mass",
        choices=DrifterWormhole.MassStatus.choices,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    eol = forms.BooleanField(
        label="End of Life (less than 4h remaining)",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    bookmark = forms.CharField(
        label="Bookmark name",
        required=False,
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "in-game bookmark at the wormhole, e.g. BAR entry Jita",
                "autocomplete": "off",
            }
        ),
    )
    notes = forms.CharField(
        label="Notes",
        required=False,
        max_length=128,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 2,
                "maxlength": 128,
                "placeholder": "optional, max. 128 characters",
            }
        ),
    )

    report_another = forms.BooleanField(
        label="Report another wormhole after saving",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def clean_system_name(self):
        """Validate the system name and store the resolved object."""
        name = self.cleaned_data["system_name"]
        self.cleaned_data["system"] = resolve_kspace_system(name)
        return name

    def clean(self):
        """
        Normal wormholes are a direct connection, so they require the
        destination system. For drifter wormholes both extra fields are
        cleared: drifters connect through their network, and their
        lifetime is fixed.
        """
        cleaned = super().clean()
        hive = cleaned.get("hive")

        if hive == DrifterWormhole.Hive.NORMAL:
            # Type code: validate against the catalog and auto-fill
            # size/lifetime where the user left them empty. A manual
            # lifetime always wins over the catalog value.
            code = (cleaned.get("wh_type") or "").strip().upper()
            if code:
                if wh_types.get_type(code) is None:
                    self.add_error(
                        "wh_type",
                        f"Unknown wormhole type '{code}'.",
                    )
                else:
                    cleaned["wh_type"] = code
                    if not cleaned.get("size"):
                        cleaned["size"] = wh_types.size_for(code)
                    if not cleaned.get("lifetime_hours"):
                        cleaned["lifetime_hours"] = wh_types.lifetime_for(code)

            destination_name = (cleaned.get("destination_name") or "").strip()
            if not destination_name:
                self.add_error(
                    "destination_name",
                    "Normal wormholes need a destination system.",
                )
            else:
                destination = resolve_any_system(destination_name)
                system = cleaned.get("system")
                if system and destination.id == system.id:
                    self.add_error(
                        "destination_name",
                        "Destination must differ from the system.",
                    )
                else:
                    cleaned["destination_system"] = destination
        else:
            cleaned["wh_type"] = ""
            cleaned["destination_system"] = None
            cleaned["lifetime_hours"] = None
            cleaned["size"] = ""

        return cleaned


class RouteForm(forms.Form):
    """Form for the route search (view-only users)."""

    start_name = forms.CharField(
        label="Start system",
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g. Jita",
                "autocomplete": "off",
                "data-system-autocomplete": "1",
            }
        ),
    )
    dest_name = forms.CharField(
        label="Destination system",
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g. Amarr",
                "autocomplete": "off",
                "data-system-autocomplete": "1",
            }
        ),
    )
    use_normal_wh = forms.BooleanField(
        label="Use normal wormholes",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    use_bridges = forms.BooleanField(
        label="Use jump bridges",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    use_drifters = forms.BooleanField(
        label="Use drifter wormholes as shortcuts",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def clean_start_name(self):
        name = self.cleaned_data["start_name"]
        self.cleaned_data["start_system"] = resolve_any_system(name)
        return name

    def clean_dest_name(self):
        name = self.cleaned_data["dest_name"]
        self.cleaned_data["dest_system"] = resolve_any_system(name)
        return name


class JumpBridgeForm(forms.Form):
    """Form for adding a jump bridge connection."""

    from_name = forms.CharField(
        label="From system",
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g. 4-HWWF",
                "autocomplete": "off",
                "data-system-autocomplete": "1",
            }
        ),
    )
    to_name = forms.CharField(
        label="To system",
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g. UALX-3",
                "autocomplete": "off",
                "data-system-autocomplete": "1",
            }
        ),
    )
    structure_name = forms.CharField(
        label="Structure name",
        required=False,
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "optional, in-game structure name",
                "autocomplete": "off",
            }
        ),
    )

    def clean_from_name(self):
        name = self.cleaned_data["from_name"]
        self.cleaned_data["from_system"] = resolve_kspace_system(name)
        return name

    def clean_to_name(self):
        name = self.cleaned_data["to_name"]
        self.cleaned_data["to_system"] = resolve_kspace_system(name)
        return name

    def clean(self):
        cleaned = super().clean()
        from_system = cleaned.get("from_system")
        to_system = cleaned.get("to_system")
        if from_system and to_system and from_system.id == to_system.id:
            raise forms.ValidationError(
                "From and to system must be different."
            )
        return cleaned


class JumpBridgeImportForm(forms.Form):
    """Bulk import form: one bridge per line, common formats accepted."""

    import_text = forms.CharField(
        label="Bridge list",
        widget=forms.Textarea(
            attrs={
                "class": "form-control font-monospace",
                "rows": 8,
                "placeholder": "1045899402916 Y-2ANO --> KVN-36\n"
                               "1045899402917 1DQ1-A --> T5ZI-S\n"
                               "one bridge per line",
            }
        ),
    )
    replace_existing = forms.BooleanField(
        label="Replace ALL existing bridges with this list",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

