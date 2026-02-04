from django.core.management.base import BaseCommand

from caixa_nfse.auditoria.models import RegistroAuditoria


class Command(BaseCommand):
    help = "Verifica a integridade da cadeia de hash dos registros de auditoria."

    def handle(self, *args, **options):
        self.stdout.write("Iniciando verificação de integridade da auditoria...")

        is_valid, broken_records = RegistroAuditoria.verificar_integridade()

        if is_valid:
            self.stdout.write(
                self.style.SUCCESS(
                    "✅ Integridade da Auditoria confirmada! Todos os hashes são válidos."
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(
                    f"❌ FALHA DE INTEGRIDADE! {len(broken_records)} registros comprometidos."
                )
            )
            for error in broken_records:
                self.stdout.write(
                    self.style.WARNING(
                        f"Registro {error['id']}: Esperado {error['expected'][:10]}..., Encontrado {error['found'][:10]}..."
                    )
                )
