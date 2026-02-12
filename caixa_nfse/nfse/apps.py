from django.apps import AppConfig


class NfseConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "caixa_nfse.nfse"
    verbose_name = "NFS-e"

    def ready(self):
        import caixa_nfse.nfse.signals  # noqa: F401
