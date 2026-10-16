from django.apps import AppConfig


class AuditConfig(AppConfig):
    # Uses BigAutoField as the default for automatically generated primary keys.
    default_auto_field = "django.db.models.BigAutoField"

    # Identifies the app's full Python package path.
    name = "apps.audit"