from django.core.management.base import BaseCommand
from django.test import RequestFactory

from caixa_nfse.auditoria.middleware import AuditMiddleware
from caixa_nfse.auditoria.models import RegistroAuditoria
from caixa_nfse.core.models import Tenant, User


class Command(BaseCommand):
    help = "Executa teste funcional da auditoria."

    def handle(self, *args, **options):
        self.stdout.write(">>> Iniciando Verificação de Auditoria (Management Command) <<<")

        # 1. Verificar Auto-Discovery (Model Audit)
        self.stdout.write("\n[1] Verificando Auditoria de Model (Tenant)...")

        # Cleanup
        Tenant.objects.filter(cnpj="99.999.999/9999-99").delete()

        # Create
        try:
            t = Tenant.objects.create(
                razao_social="Tenant Teste Audit Shell",
                cnpj="99.999.999/9999-99",
                logradouro="Rua Teste",
                numero="123",
                bairro="Centro",
                cidade="Cidade Teste",
                uf="SP",
                cep="00000000",
                codigo_ibge="0000000",
            )
            log_create = RegistroAuditoria.objects.filter(
                tabela="Tenant", registro_id=str(t.pk), acao="CREATE"
            ).first()
            if log_create:
                self.stdout.write(self.style.SUCCESS(f"✅ CREATE Log encontrado: {log_create}"))
            else:
                self.stdout.write(self.style.ERROR("❌ CREATE Log NÃO encontrado!"))

            # Update
            t.razao_social = "Tenant Teste Audit Shell Updated"
            t.save()
            log_update = RegistroAuditoria.objects.filter(
                tabela="Tenant", registro_id=str(t.pk), acao="UPDATE"
            ).first()
            if log_update:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ UPDATE Log encontrado. Diff: {log_update.campos_alterados}"
                    )
                )
            else:
                self.stdout.write(self.style.ERROR("❌ UPDATE Log NÃO encontrado!"))

            # 2. Verificar Middleware (View Audit)
            self.stdout.write("\n[2] Verificando Auditoria de View (Middleware)...")
            factory = RequestFactory()
            request = factory.get("/dashboard/?test=audit_cmd")

            # Mock user
            user = User.objects.filter(is_superuser=True).first()
            if not user:
                self.stdout.write(
                    self.style.WARNING("⚠️ Nenhum usuário superuser encontrado para teste de view.")
                )
            else:
                request.user = user
                middleware = AuditMiddleware(lambda r: None)
                middleware(request)

                log_view = (
                    RegistroAuditoria.objects.filter(
                        acao="VIEW", justificativa__contains="audit_cmd"
                    )
                    .order_by("-created_at")
                    .first()
                )
                if log_view:
                    self.stdout.write(
                        self.style.SUCCESS(f"✅ VIEW Log encontrado: {log_view.justificativa}")
                    )
                else:
                    self.stdout.write(self.style.ERROR("❌ VIEW Log NÃO encontrado!"))

            # 3. Limpeza
            self.stdout.write("\n[3] Limpeza...")
            t_pk = t.pk
            t.delete()
            log_delete = RegistroAuditoria.objects.filter(
                tabela="Tenant", registro_id=str(t_pk), acao="DELETE"
            ).first()
            if log_delete:
                self.stdout.write(self.style.SUCCESS("✅ DELETE Log encontrado."))
            else:
                self.stdout.write(self.style.ERROR("❌ DELETE Log NÃO encontrado!"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Erro durante teste: {str(e)}"))

        self.stdout.write("\n>>> Verificação Concluída <<<")
