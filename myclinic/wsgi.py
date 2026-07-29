"""WSGI entry point, used by gunicorn or Apache."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myclinic.settings")

application = get_wsgi_application()
