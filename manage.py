#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path


def load_dotenv():
    """Read a .env file next to manage.py, if one exists. Keeps secrets out of git."""
    env_file = Path(__file__).resolve().parent / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def main():
    load_dotenv()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myclinic.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Is the virtual environment activated?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
