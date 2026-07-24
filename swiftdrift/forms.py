"""
Forms of the app.

Systems are entered via a text field with autocomplete and resolved
server-side against the SDE database (eve_sde). This is more robust than
a dropdown with ~5000 entries.
"""

from django import forms

from eve_sde.models import SolarSystem

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
        label="Hive",
        choices=DrifterWormhole.Hive.choices,
        widget=forms.Select(attrs={"class": "form-select"}),
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
    notes = forms.CharField(
        label="Notes",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 2,
                "placeholder": "optional, e.g. bookmark name",
            }
        ),
    )

    def clean_system_name(self):
        """Validate the system name and store the resolved object."""
        name = self.cleaned_data["system_name"]
        self.cleaned_data["system"] = resolve_kspace_system(name)
        return name


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
    use_drifters = forms.BooleanField(
        label="Use drifter wormholes as shortcuts",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def clean_start_name(self):
        name = self.cleaned_data["start_name"]
        self.cleaned_data["start_system"] = resolve_kspace_system(name)
        return name

    def clean_dest_name(self):
        name = self.cleaned_data["dest_name"]
        self.cleaned_data["dest_system"] = resolve_kspace_system(name)
        return name
