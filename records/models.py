"""Clinical records: patients, visits, diagnoses, medications, staff."""

from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

phone_validator = RegexValidator(
    regex=r"^[\d+()\-\s]{5,20}$",
    message="Use digits, spaces, and + ( ) - only.",
)


class TimeStampedModel(models.Model):
    """Every record knows when it was written and when it last changed."""

    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        abstract = True


class Patient(TimeStampedModel):
    class Sex(models.TextChoices):
        FEMALE = "F", "Female"
        MALE = "M", "Male"
        OTHER = "O", "Other or not stated"

    # Assigned automatically on first save (see save()). Staff quote this number
    # on paper forms and over the phone, so it stays short and never changes.
    mrn = models.CharField("File number", max_length=12, unique=True, blank=True, editable=False)

    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    dob = models.DateField("Date of birth")
    sex = models.CharField(max_length=1, choices=Sex.choices, default=Sex.OTHER)

    phone = models.CharField(max_length=20, blank=True, validators=[phone_validator])
    email = models.EmailField(blank=True)
    village = models.CharField("Village or area", max_length=100, blank=True)
    address = models.TextField(blank=True)

    allergies = models.TextField(
        blank=True,
        help_text="Anything that must be seen before prescribing. Leave empty if none known.",
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(
        "Currently under care",
        default=True,
        help_text="Uncheck instead of deleting when someone moves away or dies.",
    )

    class Meta:
        ordering = ["last_name", "first_name"]
        indexes = [
            models.Index(fields=["last_name", "first_name"]),
            models.Index(fields=["dob"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["first_name", "last_name", "dob"],
                name="unique_patient_identity",
                violation_error_message="A patient with this name and date of birth already exists.",
            )
        ]

    def __str__(self):
        return f"{self.last_name}, {self.first_name}"

    def get_absolute_url(self):
        return reverse("records:patient_detail", args=[self.pk])

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.mrn:
            self.mrn = f"P{self.pk:05d}"
            # update() rather than save() so we don't recurse.
            Patient.objects.filter(pk=self.pk).update(mrn=self.mrn)

    def clean(self):
        if self.dob and self.dob > timezone.localdate():
            raise ValidationError({"dob": "Date of birth cannot be in the future."})

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self):
        """Whole years, or None if the date of birth is missing."""
        if not self.dob:
            return None
        today = timezone.localdate()
        return today.year - self.dob.year - ((today.month, today.day) < (self.dob.month, self.dob.day))

    @property
    def has_allergies(self):
        return bool(self.allergies.strip())


class Visit(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "In progress"
        CLOSED = "closed", "Finished"
        REFERRED = "referred", "Referred on"

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="visits")
    # Editable, unlike auto_now_add: paper notes often get typed up the next day.
    date = models.DateTimeField(default=timezone.now)
    reason = models.CharField("Reason for visit", max_length=200)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    seen_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="visits_seen",
    )

    class Meta:
        ordering = ["-date"]
        indexes = [models.Index(fields=["-date"]), models.Index(fields=["status"])]

    def __str__(self):
        return f"{self.patient} — {timezone.localtime(self.date):%d %b %Y}"

    def get_absolute_url(self):
        return reverse("records:visit_detail", args=[self.pk])

    def clean(self):
        if self.date and self.date > timezone.now():
            raise ValidationError({"date": "A visit cannot be recorded for a future date."})


class Diagnosis(TimeStampedModel):
    visit = models.ForeignKey(Visit, on_delete=models.CASCADE, related_name="diagnoses")
    description = models.CharField(max_length=200)
    icd_code = models.CharField("ICD-10 code", max_length=20, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "diagnoses"

    def __str__(self):
        return f"{self.description} ({self.icd_code})" if self.icd_code else self.description


class Medication(TimeStampedModel):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="medications")
    visit = models.ForeignKey(
        Visit, on_delete=models.SET_NULL, null=True, blank=True, related_name="medications"
    )
    name = models.CharField(max_length=100)
    dosage = models.CharField(max_length=100, blank=True, help_text="e.g. 500 mg, twice daily")
    start_date = models.DateField(default=date.today)
    end_date = models.DateField(null=True, blank=True, help_text="Leave empty if ongoing.")

    class Meta:
        ordering = ["-start_date", "name"]
        indexes = [models.Index(fields=["patient", "-start_date"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__isnull=True) | models.Q(end_date__gte=models.F("start_date")),
                name="medication_ends_after_start",
            )
        ]

    def __str__(self):
        return f"{self.name} for {self.patient}"

    def clean(self):
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "The end date is before the start date."})

    @property
    def is_current(self):
        today = timezone.localdate()
        return self.start_date <= today and (self.end_date is None or self.end_date >= today)


class StaffProfile(TimeStampedModel):
    class Role(models.TextChoices):
        DOCTOR = "doctor", "Doctor"
        NURSE = "nurse", "Nurse"
        CLERK = "clerk", "Records clerk"
        ADMIN = "admin", "Administrator"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff_profile"
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.NURSE)
    phone = models.CharField(max_length=20, blank=True, validators=[phone_validator])

    def __str__(self):
        return f"{self.user.get_username()} ({self.get_role_display()})"

    @property
    def can_prescribe(self):
        return self.role in {self.Role.DOCTOR, self.Role.NURSE}
