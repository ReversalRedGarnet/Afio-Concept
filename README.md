# Clinic records

A small patient-records system for a single rural clinic: patients, visits,
diagnoses, medications, and staff accounts. Built with Django and SQLite so it
runs on one laptop, with or without an internet connection.

## What it does

- **Register** — search patients by name, file number, phone, or village. Paginated,
  and it hides people no longer under care unless you ask for them.
- **Patient file** — one page per person: contact details, allergy warning, the
  medications running right now, and the full visit history.
- **Visits** — record a visit with a date you choose (so paper notes can be typed up
  later), the reason, notes, who saw the patient, and whether it's still open.
- **Diagnoses** — attached to a visit, with an optional ICD-10 code.
- **Medications** — attached to a patient, optionally to the visit that started them.
  One click marks a course finished today.
- **Staff accounts** — nothing is visible until you sign in. Roles (doctor, nurse,
  records clerk, administrator) live on a profile created automatically with each user.
- **Admin site** — bulk edits, search, and inline visits/medications per patient.

## Getting started

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000/ and sign in.

Want data to click around in?

```bash
python manage.py seed_demo --patients 30    # signs in as nurse / clinicdemo2026
```

Run the tests any time you change something:

```bash
python manage.py test
```

## Layout

```
manage.py               loads .env, then hands off to Django
myclinic/settings.py    all environment-driven; safe defaults for development
records/models.py       Patient, Visit, Diagnosis, Medication, StaffProfile
records/forms.py        widgets and validation live here, not in templates
records/views.py        class-based views, all behind a login
records/urls.py         namespaced as "records:" (e.g. records:patient_detail)
records/tests.py        25 tests: model rules, access control, view behaviour
records/management/commands/
    seed_demo.py        fake but believable data for development
    backup_db.py        timestamped, consistent SQLite copies
static/css/clinic.css   one stylesheet, no web fonts, works offline
templates/              base layout and the sign-in page
```

## Running it for real

1. Copy `.env.example` to `.env` and fill it in. At minimum set a long random
   `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, and the hostname or IP in
   `DJANGO_ALLOWED_HOSTS`. Generate a key with:
   `python -c "import secrets; print(secrets.token_urlsafe(64))"`
2. `python manage.py collectstatic`
3. `python manage.py check --deploy` should come back clean.
4. Serve it with a real server, e.g. `gunicorn myclinic.wsgi` behind nginx or
   Caddy for HTTPS. WhiteNoise handles the CSS, so no static-file config is needed.
5. Schedule backups. `python manage.py backup_db` writes a consistent copy into
   `backups/` and keeps the last 14. A daily cron entry plus a weekly copy onto a
   USB stick kept somewhere else is the whole disaster plan for a clinic this size.

SQLite is configured with write-ahead logging and a 20-second busy timeout, which
comfortably handles a few people saving at once on a local network. If the clinic
grows past that, move `DATABASES` to PostgreSQL — nothing else has to change.

## Before it holds real patient data

This is a solid skeleton, and it is not yet a system a clinic should trust with
identifiable records. What's still missing:

- **Encryption at rest.** The database file is plain SQLite. Anyone with the laptop
  has every record. Use full-disk encryption at the very least.
- **An audit trail.** Records store who saw a patient and when a row changed, but
  not who *read* a file. Most health-record rules require read logging.
- **Permissions per role.** `StaffProfile.role` exists and is unused by the views —
  every signed-in user can see and edit everything. Enforce it in `StaffOnly` before
  going live.
- **Soft delete.** Deleting a patient really deletes their visits and medications.
  `is_active` is the intended path; consider removing the delete view entirely.
- **Whatever your jurisdiction requires** for retention, consent, and breach
  reporting. That's a paperwork question, not a code question, and it comes first.
