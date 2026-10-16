from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"

    # The app is inside the project's apps package.
    name = "apps.notifications"