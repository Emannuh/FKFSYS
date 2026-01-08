from django.apps import AppConfig


class MatchesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'matches'
    
    def ready(self):

        # Import signals to activate them
        import matches.signals
        # ⬆⬆⬆ ADD THESE 2 LINES ⬆⬆⬆