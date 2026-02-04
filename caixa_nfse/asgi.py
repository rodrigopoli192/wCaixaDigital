"""
ASGI config for caixa_nfse project.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "caixa_nfse.settings.local")

application = get_asgi_application()
