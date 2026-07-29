from django.apps import AppConfig


class RecordsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "records"
    verbose_name = "Clinic records"

    def ready(self):
        from . import signals  # noqa: F401  (registers the signal handlers)
