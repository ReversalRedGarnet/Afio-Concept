"""Tests. Run them with: python manage.py test

They cover the three things most likely to break silently: automatic file
numbers, the validation rules, and whether a stranger can read patient data.
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Diagnosis, Medication, Patient, StaffProfile, Visit


class PatientModelTests(TestCase):
    def test_file_number_is_assigned_on_save(self):
        patient = Patient.objects.create(first_name="Grace", last_name="Aru", dob=date(1990, 5, 2))
        self.assertEqual(patient.mrn, f"P{patient.pk:05d}")
        patient.refresh_from_db()
        self.assertEqual(patient.mrn, f"P{patient.pk:05d}")

    def test_file_number_is_not_reassigned_on_later_saves(self):
        patient = Patient.objects.create(first_name="Peter", last_name="Beni", dob=date(1980, 1, 1))
        original = patient.mrn
        patient.phone = "+677 12345"
        patient.save()
        self.assertEqual(patient.mrn, original)

    def test_age_is_calculated_from_date_of_birth(self):
        today = timezone.localdate()
        patient = Patient(dob=today.replace(year=today.year - 30) - timedelta(days=1))
        self.assertEqual(patient.age, 30)

    def test_future_date_of_birth_is_rejected(self):
        patient = Patient(first_name="A", last_name="B", dob=timezone.localdate() + timedelta(days=1))
        with self.assertRaises(ValidationError):
            patient.full_clean()

    def test_allergy_flag(self):
        self.assertFalse(Patient(allergies="   ").has_allergies)
        self.assertTrue(Patient(allergies="Penicillin").has_allergies)


class VisitAndMedicationTests(TestCase):
    def setUp(self):
        self.patient = Patient.objects.create(first_name="Mary", last_name="Kalo", dob=date(1975, 3, 9))

    def test_visit_date_can_be_backdated(self):
        """The old model used auto_now_add, which made typing up paper notes impossible."""
        yesterday = timezone.now() - timedelta(days=1)
        visit = Visit.objects.create(patient=self.patient, reason="Cough", date=yesterday)
        self.assertEqual(visit.date, yesterday)

    def test_future_visit_is_rejected(self):
        visit = Visit(patient=self.patient, reason="Cough", date=timezone.now() + timedelta(days=2))
        with self.assertRaises(ValidationError):
            visit.full_clean()

    def test_medication_end_before_start_is_rejected(self):
        med = Medication(patient=self.patient, name="Paracetamol",
                         start_date=date(2026, 5, 10), end_date=date(2026, 5, 1))
        with self.assertRaises(ValidationError):
            med.full_clean()

    def test_is_current_reflects_dates(self):
        today = timezone.localdate()
        running = Medication(patient=self.patient, name="Metformin", start_date=today)
        finished = Medication(patient=self.patient, name="Amoxicillin",
                              start_date=today - timedelta(days=10),
                              end_date=today - timedelta(days=3))
        self.assertTrue(running.is_current)
        self.assertFalse(finished.is_current)

    def test_deleting_a_visit_keeps_the_medication(self):
        visit = Visit.objects.create(patient=self.patient, reason="Fever")
        Medication.objects.create(patient=self.patient, visit=visit, name="Paracetamol",
                                  start_date=date.today())
        visit.delete()
        med = Medication.objects.get()
        self.assertIsNone(med.visit)

    def test_diagnoses_are_removed_with_their_visit(self):
        visit = Visit.objects.create(patient=self.patient, reason="Fever")
        Diagnosis.objects.create(visit=visit, description="Malaria", icd_code="B54")
        visit.delete()
        self.assertEqual(Diagnosis.objects.count(), 0)


class StaffProfileTests(TestCase):
    def test_profile_is_created_with_the_user(self):
        user = User.objects.create_user("nurse_j", password="a-long-password-1")
        self.assertTrue(StaffProfile.objects.filter(user=user).exists())
        self.assertEqual(user.staff_profile.role, StaffProfile.Role.NURSE)


class AccessControlTests(TestCase):
    def setUp(self):
        self.patient = Patient.objects.create(first_name="Ruth", last_name="Sale", dob=date(2000, 7, 4))

    def test_every_page_needs_a_signed_in_user(self):
        urls = [
            reverse("records:dashboard"),
            reverse("records:patient_list"),
            reverse("records:patient_create"),
            reverse("records:patient_detail", args=[self.patient.pk]),
            reverse("records:patient_update", args=[self.patient.pk]),
            reverse("records:visit_create", args=[self.patient.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("login"), response.url)


class ViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("clerk", password="a-long-password-1")
        cls.a = Patient.objects.create(first_name="Grace", last_name="Aru", dob=date(1991, 2, 3),
                                       village="Riverside", allergies="Penicillin")
        cls.b = Patient.objects.create(first_name="Peter", last_name="Manu", dob=date(1965, 8, 21),
                                       village="Hilltop", is_active=False)

    def setUp(self):
        self.client.force_login(self.user)

    def test_dashboard_loads(self):
        response = self.client.get(reverse("records:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Today at the clinic")

    def test_list_hides_inactive_patients_by_default(self):
        response = self.client.get(reverse("records:patient_list"))
        self.assertContains(response, "Grace Aru")
        self.assertNotContains(response, "Peter Manu")

    def test_list_can_include_inactive_patients(self):
        response = self.client.get(reverse("records:patient_list"), {"include_inactive": "on"})
        self.assertContains(response, "Peter Manu")

    def test_search_matches_name_file_number_and_village(self):
        for term in ["grace", self.a.mrn, "riverside"]:
            with self.subTest(term=term):
                response = self.client.get(reverse("records:patient_list"), {"q": term})
                self.assertContains(response, "Grace Aru")

    def test_allergy_is_flagged_on_the_detail_page(self):
        response = self.client.get(self.a.get_absolute_url())
        self.assertContains(response, "Penicillin")
        self.assertContains(response, "Allergies")

    def test_creating_a_patient(self):
        response = self.client.post(reverse("records:patient_create"), {
            "first_name": " Esther ", "last_name": " Rongo ", "dob": "1988-11-30",
            "sex": "F", "phone": "+677 55512", "email": "", "village": "Mission",
            "address": "", "allergies": "", "notes": "", "is_active": "on",
        })
        self.assertEqual(response.status_code, 302)
        patient = Patient.objects.get(last_name="Rongo")
        self.assertEqual(patient.first_name, "Esther")  # whitespace trimmed
        self.assertTrue(patient.mrn)

    def test_duplicate_patient_is_refused(self):
        response = self.client.post(reverse("records:patient_create"), {
            "first_name": "Grace", "last_name": "Aru", "dob": "1991-02-03",
            "sex": "O", "is_active": "on",
        })
        self.assertEqual(response.status_code, 200)  # form redisplayed with the error
        self.assertEqual(Patient.objects.filter(last_name="Aru").count(), 1)

    def test_recording_a_visit_attributes_it_to_the_signed_in_user(self):
        response = self.client.post(reverse("records:visit_create", args=[self.a.pk]), {
            "date": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
            "reason": "Fever and headache", "notes": "Temp 38.4",
            "status": "open", "seen_by": self.user.pk,
        })
        self.assertEqual(response.status_code, 302)
        visit = Visit.objects.get()
        self.assertEqual(visit.patient, self.a)
        self.assertEqual(visit.seen_by, self.user)

    def test_adding_a_diagnosis_to_a_visit(self):
        visit = Visit.objects.create(patient=self.a, reason="Fever")
        self.client.post(reverse("records:diagnosis_create", args=[visit.pk]),
                         {"description": "Malaria, uncomplicated", "icd_code": "B54"})
        self.assertEqual(visit.diagnoses.count(), 1)

    def test_stopping_a_medication_sets_todays_date(self):
        med = Medication.objects.create(patient=self.a, name="Amoxicillin",
                                        start_date=timezone.localdate() - timedelta(days=3))
        self.client.post(reverse("records:medication_stop", args=[med.pk]))
        med.refresh_from_db()
        self.assertEqual(med.end_date, timezone.localdate())

    def test_medication_form_only_offers_this_patients_visits(self):
        mine = Visit.objects.create(patient=self.a, reason="Fever")
        theirs = Visit.objects.create(patient=self.b, reason="Cough")
        response = self.client.get(reverse("records:medication_create", args=[self.a.pk]))
        choices = response.context["form"].fields["visit"].queryset
        self.assertIn(mine, choices)
        self.assertNotIn(theirs, choices)

    def test_patient_detail_queries_do_not_grow_with_history(self):
        """Guards against the N+1 problem: 20 visits must cost the same as 5."""
        def queries_for(visit_count):
            self.a.visits.all().delete()
            for i in range(visit_count):
                visit = Visit.objects.create(patient=self.a, reason=f"Visit {i}")
                Diagnosis.objects.create(visit=visit, description="Malaria")
            with CaptureQueriesContext(connection) as ctx:
                self.client.get(self.a.get_absolute_url())
            return len(ctx.captured_queries)

        self.assertEqual(queries_for(5), queries_for(20))
