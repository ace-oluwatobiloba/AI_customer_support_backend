from django.apps import AppConfig


class ConversationsConfig(AppConfig):
    # Django will use BigAutoField for automatically generated
    # primary keys unless a model explicitly defines another type.
    default_auto_field = "django.db.models.BigAutoField"

    # This is the Python import path of our Conversations app.
    name = "apps.conversations"