"""Views. Everything here requires a signed-in staff account."""

import logging
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView,
)

from .forms import DiagnosisForm, MedicationForm, PatientForm, PatientSearchForm, VisitForm
from .models import Medication, Patient, Visit

logger = logging.getLogger("records")


class StaffOnly(LoginRequiredMixin):
    """Single place to tighten access later (e.g. role checks)."""


class Dashboard(StaffOnly, TemplateView):
    template_name = "records/dashboard.html"

    def get_context_data(self, **kwargs):
        today = timezone.localdate()
        week_ago = timezone.now() - timedelta(days=7)
        return super().get_context_data(
            patient_count=Patient.objects.filter(is_active=True).count(),
            visits_this_week=Visit.objects.filter(date__gte=week_ago).count(),
            open_visits=Visit.objects.filter(status=Visit.Status.OPEN)
                                     .select_related("patient")[:8],
            current_meds=Medication.objects.filter(
                start_date__lte=today
            ).filter(Q(end_date__isnull=True) | Q(end_date__gte=today)).count(),
            recent_visits=Visit.objects.select_related("patient")
                                       .prefetch_related("diagnoses")[:8],
            **kwargs,
        )


class PatientList(StaffOnly, ListView):
    model = Patient
    paginate_by = 25
    context_object_name = "patients"
    template_name = "records/patient_list.html"

    def get_queryset(self):
        self.search_form = PatientSearchForm(self.request.GET or None)
        # Explicit order_by: annotate() adds a GROUP BY, which makes Django treat the
        # queryset as unordered and warn about unstable pagination.
        qs = Patient.objects.annotate(visit_count=Count("visits")).order_by("last_name", "first_name")

        if self.search_form.is_valid():
            term = self.search_form.cleaned_data.get("q", "").strip()
            if not self.search_form.cleaned_data.get("include_inactive"):
                qs = qs.filter(is_active=True)
            if term:
                qs = qs.filter(
                    Q(first_name__icontains=term)
                    | Q(last_name__icontains=term)
                    | Q(mrn__icontains=term)
                    | Q(phone__icontains=term)
                    | Q(village__icontains=term)
                )
        else:
            qs = qs.filter(is_active=True)
        return qs

    def get_context_data(self, **kwargs):
        return super().get_context_data(search_form=self.search_form, **kwargs)


class PatientDetail(StaffOnly, DetailView):
    model = Patient
    context_object_name = "patient"
    template_name = "records/patient_detail.html"

    def get_queryset(self):
        # One query for the patient, one for visits, one for diagnoses, one for meds.
        return Patient.objects.prefetch_related(
            Prefetch("visits", queryset=Visit.objects.select_related("seen_by")
                                             .prefetch_related("diagnoses")),
            "medications",
        )

    def get_context_data(self, **kwargs):
        today = timezone.localdate()
        meds = list(self.object.medications.all())
        return super().get_context_data(
            current_meds=[m for m in meds if m.is_current],
            past_meds=[m for m in meds if not m.is_current],
            today=today,
            **kwargs,
        )


class PatientCreate(StaffOnly, CreateView):
    model = Patient
    form_class = PatientForm
    template_name = "records/patient_form.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        logger.info("Patient %s created by %s", self.object.mrn, self.request.user)
        messages.success(self.request, f"Added {self.object.full_name} as file {self.object.mrn}.")
        return response


class PatientUpdate(StaffOnly, UpdateView):
    model = Patient
    form_class = PatientForm
    template_name = "records/patient_form.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        logger.info("Patient %s updated by %s", self.object.mrn, self.request.user)
        messages.success(self.request, "Changes saved.")
        return response


class PatientDelete(StaffOnly, DeleteView):
    model = Patient
    template_name = "records/patient_confirm_delete.html"
    success_url = reverse_lazy("records:patient_list")

    def form_valid(self, form):
        logger.warning("Patient %s deleted by %s", self.object.mrn, self.request.user)
        messages.success(self.request, f"Deleted the file for {self.object.full_name}.")
        return super().form_valid(form)


# --- Visits -----------------------------------------------------------------

class VisitCreate(StaffOnly, CreateView):
    model = Visit
    form_class = VisitForm
    template_name = "records/visit_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.patient = get_object_or_404(Patient, pk=kwargs["patient_pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        return {"seen_by": self.request.user.pk, "date": timezone.now()}

    def form_valid(self, form):
        form.instance.patient = self.patient
        response = super().form_valid(form)
        messages.success(self.request, "Visit recorded.")
        return response

    def get_context_data(self, **kwargs):
        return super().get_context_data(patient=self.patient, **kwargs)


class VisitUpdate(StaffOnly, UpdateView):
    model = Visit
    form_class = VisitForm
    template_name = "records/visit_form.html"

    def get_context_data(self, **kwargs):
        return super().get_context_data(patient=self.object.patient, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Visit updated.")
        return super().form_valid(form)


class VisitDetail(StaffOnly, DetailView):
    model = Visit
    context_object_name = "visit"
    template_name = "records/visit_detail.html"

    def get_queryset(self):
        return Visit.objects.select_related("patient", "seen_by").prefetch_related(
            "diagnoses", "medications"
        )

    def get_context_data(self, **kwargs):
        return super().get_context_data(diagnosis_form=DiagnosisForm(), **kwargs)


class DiagnosisCreate(StaffOnly, CreateView):
    form_class = DiagnosisForm
    template_name = "records/visit_detail.html"

    def dispatch(self, request, *args, **kwargs):
        self.visit = get_object_or_404(Visit, pk=kwargs["visit_pk"])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.visit = self.visit
        form.save()
        messages.success(self.request, "Diagnosis added.")
        return redirect(self.visit.get_absolute_url())

    def form_invalid(self, form):
        messages.error(self.request, "The diagnosis needs a description.")
        return redirect(self.visit.get_absolute_url())

    def get(self, request, *args, **kwargs):
        return redirect(self.visit.get_absolute_url())


# --- Medications ------------------------------------------------------------

class MedicationCreate(StaffOnly, CreateView):
    model = Medication
    form_class = MedicationForm
    template_name = "records/medication_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.patient = get_object_or_404(Patient, pk=kwargs["patient_pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "patient": self.patient}

    def form_valid(self, form):
        form.instance.patient = self.patient
        messages.success(self.request, f"Added {form.instance.name}.")
        return super().form_valid(form)

    def get_success_url(self):
        return self.patient.get_absolute_url()

    def get_context_data(self, **kwargs):
        return super().get_context_data(patient=self.patient, **kwargs)


class MedicationUpdate(StaffOnly, UpdateView):
    model = Medication
    form_class = MedicationForm
    template_name = "records/medication_form.html"

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "patient": self.object.patient}

    def get_success_url(self):
        return self.object.patient.get_absolute_url()

    def get_context_data(self, **kwargs):
        return super().get_context_data(patient=self.object.patient, **kwargs)


class MedicationStop(StaffOnly, UpdateView):
    """One click to mark a medication as finished today."""

    model = Medication
    fields = []
    http_method_names = ["post"]

    def form_valid(self, form):
        self.object.end_date = timezone.localdate()
        self.object.save(update_fields=["end_date", "updated_at"])
        messages.success(self.request, f"Marked {self.object.name} as finished today.")
        return redirect(self.object.patient.get_absolute_url())
