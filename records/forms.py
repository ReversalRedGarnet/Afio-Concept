"""Forms. Widgets are set here so the templates stay dumb."""

from datetime import datetime

from django import forms
from django.utils import timezone

from .models import Diagnosis, Medication, Patient, Visit


class StyledFormMixin:
    """Give every widget the same CSS hook and mark required fields."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            css = widget.attrs.get("class", "")
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = f"{css} check".strip()
            else:
                widget.attrs["class"] = f"{css} input".strip()
            if field.required:
                widget.attrs["aria-required"] = "true"


class DateInput(forms.DateInput):
    input_type = "date"  # native date picker, no JavaScript needed


class DateTimeInput(forms.DateTimeInput):
    input_type = "datetime-local"

    def format_value(self, value):
        """HTML datetime-local wants 2026-07-30T09:15, not Django's display format.

        Django hands this widget an aware datetime, a naive one, or an already
        formatted string depending on where the value came from, so handle all three.
        """
        if value in (None, ""):
            return ""
        if isinstance(value, datetime):
            if timezone.is_aware(value):
                value = timezone.localtime(value)
            return value.strftime("%Y-%m-%dT%H:%M")
        return str(value).replace(" ", "T")[:16]


class PatientForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Patient
        fields = [
            "first_name", "last_name", "dob", "sex",
            "phone", "email", "village", "address",
            "allergies", "notes", "is_active",
        ]
        widgets = {
            "dob": DateInput(),
            "address": forms.Textarea(attrs={"rows": 2}),
            "allergies": forms.Textarea(attrs={"rows": 2}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_first_name(self):
        return self.cleaned_data["first_name"].strip()

    def clean_last_name(self):
        return self.cleaned_data["last_name"].strip()


class VisitForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Visit
        fields = ["date", "reason", "notes", "status", "seen_by"]
        widgets = {
            "date": DateTimeInput(),
            "notes": forms.Textarea(attrs={"rows": 6}),
        }


class DiagnosisForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Diagnosis
        fields = ["description", "icd_code"]


class MedicationForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Medication
        fields = ["name", "dosage", "start_date", "end_date", "visit"]
        widgets = {"start_date": DateInput(), "end_date": DateInput()}

    def __init__(self, *args, patient=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.patient = patient or getattr(self.instance, "patient", None)
        # Only offer visits belonging to this patient.
        if self.patient and self.patient.pk:
            self.fields["visit"].queryset = self.patient.visits.all()
            self.fields["visit"].label = "Started at visit (optional)"
        else:
            self.fields.pop("visit")


class PatientSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        label="Search",
        widget=forms.TextInput(attrs={
            "class": "input",
            "placeholder": "Name, file number, phone, or village",
            "autofocus": "autofocus",
        }),
    )
    include_inactive = forms.BooleanField(
        required=False, label="Include people no longer under care",
        widget=forms.CheckboxInput(attrs={"class": "check"}),
    )
