from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html

from .models import Diagnosis, Medication, Patient, StaffProfile, Visit


class DiagnosisInline(admin.TabularInline):
    model = Diagnosis
    extra = 1


class MedicationInline(admin.TabularInline):
    model = Medication
    extra = 0
    fields = ["name", "dosage", "start_date", "end_date"]


class VisitInline(admin.TabularInline):
    model = Visit
    extra = 0
    fields = ["date", "reason", "status", "seen_by"]
    show_change_link = True


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ["mrn", "last_name", "first_name", "age", "village", "flag", "is_active"]
    list_filter = ["is_active", "sex", "village"]
    search_fields = ["mrn", "first_name", "last_name", "phone", "village"]
    ordering = ["last_name", "first_name"]
    readonly_fields = ["mrn", "created_at", "updated_at"]
    inlines = [VisitInline, MedicationInline]
    date_hierarchy = "created_at"

    @admin.display(description="Allergies")
    def flag(self, obj):
        if obj.has_allergies:
            return format_html('<strong style="color:#a4232b">allergy</strong>')
        return "—"


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = ["date", "patient", "reason", "status", "seen_by"]
    list_filter = ["status", "date"]
    search_fields = ["patient__last_name", "patient__mrn", "reason", "notes"]
    autocomplete_fields = ["patient"]
    inlines = [DiagnosisInline]
    date_hierarchy = "date"


@admin.register(Medication)
class MedicationAdmin(admin.ModelAdmin):
    list_display = ["name", "patient", "dosage", "start_date", "end_date", "is_current"]
    list_filter = ["start_date"]
    search_fields = ["name", "patient__last_name", "patient__mrn"]
    autocomplete_fields = ["patient", "visit"]


@admin.register(Diagnosis)
class DiagnosisAdmin(admin.ModelAdmin):
    list_display = ["description", "icd_code", "visit"]
    search_fields = ["description", "icd_code"]
    autocomplete_fields = ["visit"]


class StaffProfileInline(admin.StackedInline):
    model = StaffProfile
    can_delete = False


class UserAdmin(BaseUserAdmin):
    inlines = [StaffProfileInline]
    list_display = ["username", "first_name", "last_name", "role", "is_active", "is_staff"]

    @admin.display(description="Role")
    def role(self, obj):
        profile = getattr(obj, "staff_profile", None)
        return profile.get_role_display() if profile else "—"


admin.site.unregister(User)
admin.site.register(User, UserAdmin)

admin.site.site_header = "Clinic records"
admin.site.site_title = "Clinic records"
admin.site.index_title = "Administration"
