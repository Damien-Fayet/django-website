from django.apps import AppConfig


class Avent2025Config(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'avent2025'
    
    def ready(self):
        """Importer les signaux quand l'app est prête"""
        import avent2025.signals
