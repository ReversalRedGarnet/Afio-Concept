"""Fill the database with believable fake data so you can click around.

    python manage.py seed_demo --patients 30

Never run this against a database holding real patients.
"""

import random
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from records.models import Diagnosis, Medication, Patient, StaffProfile, Visit

FIRST = ["Grace", "Peter", "Mary", "John", "Esther", "Samuel", "Ruth", "Daniel",
         "Naomi", "Joseph", "Hannah", "Michael", "Sarah", "Thomas", "Lydia"]
LAST = ["Aru", "Beni", "Kalo", "Manu", "Rongo", "Sale", "Tuki", "Vaea",
        "Waena", "Loko", "Mera", "Nako"]
VILLAGES = ["Riverside", "Hilltop", "East Bay", "Mission", "Old Landing", "Ridge"]
REASONS = ["Fever and headache", "Cough for one week", "Antenatal check",
           "Cut on left hand", "Blood pressure review", "Child immunisation",
           "Stomach pain", "Skin infection", "Follow-up on malaria treatment"]
DIAGNOSES = [("Malaria, uncomplicated", "B54"), ("Upper respiratory infection", "J06.9"),
             ("Hypertension", "I10"), ("Type 2 diabetes", "E11"),
             ("Skin abscess", "L02"), ("Gastroenteritis", "A09")]
DRUGS = [("Paracetamol", "500 mg, three times daily"), ("Amoxicillin", "250 mg, three times daily"),
         ("Metformin", "500 mg, twice daily"), ("Amlodipine", "5 mg, once daily"),
         ("Artemether-lumefantrine", "as per weight, twice daily for 3 days")]
ALLERGIES = ["", "", "", "", "Penicillin — rash", "Sulfa drugs", "Aspirin — asthma flare"]


class Command(BaseCommand):
    help = "Create demo staff, patients, visits, diagnoses and medications."

    def add_arguments(self, parser):
        parser.add_argument("--patients", type=int, default=25)
        parser.add_argument("--seed", type=int, default=1, help="Random seed, for repeatable data.")
        parser.add_argument("--force", action="store_true", help="Allow seeding when DEBUG is off.")

    def handle(self, *args, **options):
        from django.conf import settings
        if not settings.DEBUG and not options.get("force"):
            raise CommandError("Refusing to seed demo data while DEBUG is off.")

        random.seed(options["seed"])

        nurse, created = User.objects.get_or_create(
            username="nurse", defaults={"first_name": "Demo", "last_name": "Nurse"}
        )
        if created:
            nurse.set_password("clinicdemo2026")
            nurse.save()
        StaffProfile.objects.update_or_create(user=nurse, defaults={"role": StaffProfile.Role.NURSE})

        made = 0
        for _ in range(options["patients"]):
            first, last = random.choice(FIRST), random.choice(LAST)
            dob = date.today() - timedelta(days=random.randint(400, 30000))
            if Patient.objects.filter(first_name=first, last_name=last, dob=dob).exists():
                continue
            patient = Patient.objects.create(
                first_name=first, last_name=last, dob=dob,
                sex=random.choice(Patient.Sex.values),
                phone=f"+677 {random.randint(10000, 99999)}",
                village=random.choice(VILLAGES),
                allergies=random.choice(ALLERGIES),
            )
            made += 1

            for _ in range(random.randint(0, 4)):
                visit = Visit.objects.create(
                    patient=patient,
                    date=timezone.now() - timedelta(days=random.randint(0, 400),
                                                    hours=random.randint(0, 8)),
                    reason=random.choice(REASONS),
                    notes="Observations recorded on the paper card and typed up here.",
                    status=random.choice([Visit.Status.CLOSED, Visit.Status.CLOSED,
                                          Visit.Status.OPEN, Visit.Status.REFERRED]),
                    seen_by=nurse,
                )
                if random.random() < 0.7:
                    description, code = random.choice(DIAGNOSES)
                    Diagnosis.objects.create(visit=visit, description=description, icd_code=code)
                if random.random() < 0.5:
                    name, dosage = random.choice(DRUGS)
                    start = timezone.localtime(visit.date).date()
                    Medication.objects.create(
                        patient=patient, visit=visit, name=name, dosage=dosage,
                        start_date=start,
                        end_date=None if random.random() < 0.4 else start + timedelta(days=random.randint(3, 90)),
                    )

        self.stdout.write(self.style.SUCCESS(
            f"Created {made} patients. Sign in as 'nurse' / 'clinicdemo2026'."
        ))
