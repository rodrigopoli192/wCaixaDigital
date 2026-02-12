"""
Management command to check protocol payment deadlines.
Marks overdue protocols as VENCIDO and creates notifications.
"""

from datetime import date

from django.core.management.base import BaseCommand

from caixa_nfse.caixa.models import MovimentoImportado, StatusRecebimento
from caixa_nfse.core.models import Notificacao, TipoNotificacao


class Command(BaseCommand):
    help = "Check protocol deadlines, mark VENCIDO, and create notifications."

    def handle(self, *args, **options):
        hoje = date.today()

        # Mark overdue protocols
        vencidos = MovimentoImportado.objects.filter(
            prazo_quitacao__lt=hoje,
            status_recebimento__in=[
                StatusRecebimento.PENDENTE,
                StatusRecebimento.PARCIAL,
            ],
        )

        count_vencidos = 0
        for imp in vencidos:
            imp.status_recebimento = StatusRecebimento.VENCIDO
            imp.save(update_fields=["status_recebimento"])
            count_vencidos += 1

            # Create notification for each overdue protocol
            Notificacao.objects.get_or_create(
                tenant=imp.tenant,
                tipo=TipoNotificacao.PROTOCOLO_VENCIDO,
                referencia_id=str(imp.pk),
                lida=False,
                defaults={
                    "titulo": f"Protocolo {imp.protocolo} vencido",
                    "mensagem": (
                        f"O protocolo {imp.protocolo} ({imp.descricao}) "
                        f"tinha prazo até {imp.prazo_quitacao.strftime('%d/%m/%Y')} "
                        f"e possui saldo pendente de R$ {imp.saldo_pendente:.2f}."
                    ),
                },
            )

        self.stdout.write(
            self.style.SUCCESS(f"{count_vencidos} protocolo(s) marcado(s) como VENCIDO.")
        )

        # Notify about protocols expiring soon (within 3 days)
        from datetime import timedelta

        prazo_alerta = hoje + timedelta(days=3)
        vencendo = MovimentoImportado.objects.filter(
            prazo_quitacao__range=(hoje, prazo_alerta),
            status_recebimento__in=[
                StatusRecebimento.PENDENTE,
                StatusRecebimento.PARCIAL,
            ],
        )

        count_alertas = 0
        for imp in vencendo:
            _, created = Notificacao.objects.get_or_create(
                tenant=imp.tenant,
                tipo=TipoNotificacao.PROTOCOLO_VENCENDO,
                referencia_id=str(imp.pk),
                lida=False,
                defaults={
                    "titulo": f"Protocolo {imp.protocolo} vencendo",
                    "mensagem": (
                        f"O protocolo {imp.protocolo} vence em "
                        f"{imp.prazo_quitacao.strftime('%d/%m/%Y')}. "
                        f"Saldo pendente: R$ {imp.saldo_pendente:.2f}."
                    ),
                },
            )
            if created:
                count_alertas += 1

        self.stdout.write(self.style.SUCCESS(f"{count_alertas} alerta(s) de vencimento criado(s)."))
