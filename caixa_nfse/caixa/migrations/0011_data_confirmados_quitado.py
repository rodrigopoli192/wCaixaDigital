# Data migration: set confirmed MovimentoImportado to QUITADO
from django.db import migrations


def mark_confirmed_as_quitado(apps, schema_editor):
    MovimentoImportado = apps.get_model("caixa", "MovimentoImportado")
    MovimentoImportado.objects.filter(confirmado=True).update(status_recebimento="QUITADO")


def reverse_quitado(apps, schema_editor):
    MovimentoImportado = apps.get_model("caixa", "MovimentoImportado")
    MovimentoImportado.objects.filter(status_recebimento="QUITADO").update(
        status_recebimento="PENDENTE"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("caixa", "0010_recebimento_parcial"),
    ]

    operations = [
        migrations.RunPython(mark_confirmed_as_quitado, reverse_quitado),
    ]
