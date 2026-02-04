"""
Django management command to create sample data for testing.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = "Cria dados de exemplo para teste do sistema"

    def handle(self, *args, **options):
        self.stdout.write("Criando dados de exemplo...")

        # Import models
        from caixa_nfse.caixa.models import Caixa
        from caixa_nfse.clientes.models import Cliente
        from caixa_nfse.core.models import FormaPagamento, Tenant
        from caixa_nfse.nfse.models import ServicoMunicipal

        # 1. Criar Tenant
        tenant, created = Tenant.objects.get_or_create(
            cnpj="12345678000190",
            defaults={
                "razao_social": "Empresa Demonstração LTDA",
                "nome_fantasia": "Demo Corp",
                "inscricao_municipal": "123456",
                "regime_tributario": "SIMPLES",
                "email": "contato@democorp.com.br",
                "telefone": "(11) 99999-9999",
                "logradouro": "Rua Exemplo",
                "numero": "100",
                "bairro": "Centro",
                "cidade": "São Paulo",
                "uf": "SP",
                "cep": "01001-000",
                "codigo_ibge": "3550308",
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"  ✓ Tenant criado: {tenant}"))

        # 2. Criar Formas de Pagamento
        formas = [
            ("DINHEIRO", "Dinheiro"),
            ("DEBITO", "Cartão Débito"),
            ("CREDITO", "Cartão Crédito"),
            ("PIX", "PIX"),
        ]
        for tipo, nome in formas:
            fp, created = FormaPagamento.objects.get_or_create(
                tenant=tenant,
                tipo=tipo,
                defaults={
                    "nome": nome,
                    "ativo": True,
                },
            )
            if created:
                self.stdout.write(f"  ✓ Forma pagamento: {nome}")

        # 3. Criar Caixas
        for ident, tipo in [("CAIXA-01", "PRINCIPAL"), ("CAIXA-02", "SECUNDARIO")]:
            caixa, created = Caixa.objects.get_or_create(
                tenant=tenant,
                identificador=ident,
                defaults={"tipo": tipo, "status": "FECHADO"},
            )
            if created:
                self.stdout.write(f"  ✓ Caixa: {ident}")

        # 4. Criar Clientes
        clientes_data = [
            {
                "tipo_pessoa": "PJ",
                "cpf_cnpj": "98765432000156",
                "razao_social": "Cliente Teste LTDA",
                "nome_fantasia": "Cliente Teste",
                "email": "cliente@teste.com.br",
                "telefone": "(11) 98888-7777",
                "logradouro": "Av. Principal",
                "numero": "500",
                "bairro": "Jardins",
                "cidade": "São Paulo",
                "uf": "SP",
                "cep": "04543-000",
            },
            {
                "tipo_pessoa": "PF",
                "cpf_cnpj": "12345678901",
                "razao_social": "João da Silva",
                "email": "joao@email.com",
                "telefone": "(11) 97777-6666",
                "logradouro": "Rua das Flores",
                "numero": "25",
                "bairro": "Vila Nova",
                "cidade": "São Paulo",
                "uf": "SP",
                "cep": "02222-000",
            },
        ]
        for data in clientes_data:
            cliente, created = Cliente.objects.get_or_create(
                tenant=tenant,
                cpf_cnpj=data["cpf_cnpj"],
                defaults={**data, "consentimento_lgpd": True},
            )
            if created:
                self.stdout.write(f"  ✓ Cliente: {cliente.razao_social}")

        # 5. Criar Serviços LC 116
        servicos = [
            ("01.01", "Análise e desenvolvimento de sistemas"),
            ("01.02", "Programação"),
            ("17.01", "Assessoria ou consultoria"),
        ]
        for codigo, descricao in servicos:
            srv, created = ServicoMunicipal.objects.get_or_create(
                codigo_lc116=codigo,
                municipio_ibge="3550308",
                defaults={
                    "descricao": descricao,
                    "aliquota_iss": Decimal("0.05"),
                },
            )
            if created:
                self.stdout.write(f"  ✓ Serviço: {codigo}")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("✅ Dados de exemplo criados com sucesso!"))
        self.stdout.write("")
        self.stdout.write("Agora você pode:")
        self.stdout.write("  - Acessar o admin: http://localhost:8000/admin/")
        self.stdout.write("  - Acessar o dashboard: http://localhost:8000/")
