from django.apps import AppConfig


class KnowledgeConfig(AppConfig):
    # Use BigAutoField for automatically generated primary keys
    # unless a model explicitly defines another primary-key type.
    default_auto_field = "django.db.models.BigAutoField"

    # This is the actual Python import path of our Knowledge app.
    # The app lives inside the project's "apps" package.
    name = "apps.knowledge"