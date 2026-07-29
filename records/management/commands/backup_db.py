"""Copy the SQLite database to backups/ with a timestamp.

    python manage.py backup_db

Uses SQLite's own backup API, so it is safe to run while the site is being used.
Put it in cron (e.g. daily at 19:00) and copy the folder to a USB stick weekly.
"""

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Make a timestamped, consistent copy of the SQLite database."

    def add_arguments(self, parser):
        parser.add_argument("--keep", type=int, default=14, help="How many backups to retain.")

    def handle(self, *args, **options):
        db = Path(settings.DATABASES["default"]["NAME"])
        if not db.exists():
            raise CommandError(f"No database at {db}. Run migrate first.")

        folder = Path(settings.BASE_DIR) / "backups"
        folder.mkdir(exist_ok=True)
        target = folder / f"clinic-{datetime.now():%Y%m%d-%H%M}.sqlite3"

        source = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        destination = sqlite3.connect(target)
        with destination:
            source.backup(destination)
        source.close()
        destination.close()

        backups = sorted(folder.glob("clinic-*.sqlite3"))
        for old in backups[: max(0, len(backups) - options["keep"])]:
            old.unlink()

        size = target.stat().st_size / 1024
        self.stdout.write(self.style.SUCCESS(f"Backed up to {target} ({size:.0f} KB)."))
