from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"

    def ready(self):
        # Register drf-spectacular extensions at application startup.
        from apps.accounts.schema import authentication  # noqa: F401
