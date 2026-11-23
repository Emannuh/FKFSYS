from django.apps import AppConfig


class RefereesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'referees'

    def ready(self):
        from . import goal_signals  # noqa: F401  (registers signal handlers)
