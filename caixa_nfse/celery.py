"""
Celery configuration for caixa_nfse project.
"""

import os

from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "caixa_nfse.settings.local")

app = Celery("caixa_nfse")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# ── Beat Schedule ──────────────────────────────────────────
app.conf.beat_schedule = {
    "poll-nfse-status": {
        "task": "caixa_nfse.nfse.tasks.poll_nfse_status",
        "schedule": 300.0,  # Every 5 minutes
        "options": {"queue": "nfse"},
    },
    "verificar-certificados": {
        "task": "caixa_nfse.nfse.tasks.verificar_certificados_vencendo",
        "schedule": crontab(hour=8, minute=0),  # Daily at 8:00 AM
        "options": {"queue": "default"},
    },
}
app.conf.timezone = "America/Sao_Paulo"


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery."""
    print(f"Request: {self.request!r}")
