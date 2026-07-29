from django.urls import path

from . import views

app_name = "records"

urlpatterns = [
    path("", views.Dashboard.as_view(), name="dashboard"),

    # Patients
    path("patients/", views.PatientList.as_view(), name="patient_list"),
    path("patients/new/", views.PatientCreate.as_view(), name="patient_create"),
    path("patients/<int:pk>/", views.PatientDetail.as_view(), name="patient_detail"),
    path("patients/<int:pk>/edit/", views.PatientUpdate.as_view(), name="patient_update"),
    path("patients/<int:pk>/delete/", views.PatientDelete.as_view(), name="patient_delete"),

    # Visits
    path("patients/<int:patient_pk>/visits/new/", views.VisitCreate.as_view(), name="visit_create"),
    path("visits/<int:pk>/", views.VisitDetail.as_view(), name="visit_detail"),
    path("visits/<int:pk>/edit/", views.VisitUpdate.as_view(), name="visit_update"),
    path("visits/<int:visit_pk>/diagnoses/new/", views.DiagnosisCreate.as_view(), name="diagnosis_create"),

    # Medications
    path("patients/<int:patient_pk>/medications/new/", views.MedicationCreate.as_view(), name="medication_create"),
    path("medications/<int:pk>/edit/", views.MedicationUpdate.as_view(), name="medication_update"),
    path("medications/<int:pk>/stop/", views.MedicationStop.as_view(), name="medication_stop"),
]
