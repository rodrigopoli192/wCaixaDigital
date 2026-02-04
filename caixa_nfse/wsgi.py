"""
WSGI config for caixa_nfse project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "caixa_nfse.settings.local")

application = get_wsgi_application()
