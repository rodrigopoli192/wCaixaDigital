import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone

from caixa_nfse.caixa.models import (
    FechamentoCaixa,
    MovimentoCaixa,
    StatusCaixa,
    StatusFechamento,
    TipoMovimento,
)

# Helper assertions


@pytest.mark.django_db
class TestCaixaUpdateView:
    """Tests for CaixaUpdateView."""

    def test_update_caixa_success(self, client_logged, user, caixa):
        """Should update caixa successfully."""
        user.pode_aprovar_fechamento = True
        user.save()
        url = reverse("caixa:editar", kwargs={"pk": caixa.pk})
        data = {
            "identificador": "CAIXA-UPDATED",
            "tipo": "VIRTUAL",  # Correct choice
            "ativo": True,
        }
        response = client_logged.post(url, data)
        assert response.status_code == 302

        caixa.refresh_from_db()
        assert caixa.identificador == "CAIXA-UPDATED"
        assert caixa.tipo == "VIRTUAL"

    def test_update_caixa_context(self, client_logged, user, caixa):
        """Should have correct context data."""
        user.pode_aprovar_fechamento = True
        user.save()
        url = reverse("caixa:editar", kwargs={"pk": caixa.pk})
        response = client_logged.get(url)
        assert response.status_code == 200
        assert response.context["page_title"] == f"Editar {caixa.identificador}"
        assert response.context["is_edit"] is True


@pytest.mark.django_db
class TestListaMovimentosView:
    """Tests for ListaMovimentosView."""

    def test_list_movimentos(self, client_logged, abertura, forma_pagamento):
        """Should list movements for an opening."""
        # Create a movement manually
        movimento = MovimentoCaixa.objects.create(
            tenant=abertura.tenant,
            abertura=abertura,
            tipo=TipoMovimento.ENTRADA,
            forma_pagamento=forma_pagamento,
            valor=Decimal("50.00"),
            descricao="Teste Listagem",
        )

        url = reverse("caixa:lista_movimentos", kwargs={"pk": abertura.pk})
        response = client_logged.get(url)
        assert response.status_code == 200
        assert movimento in response.context["object_list"]
        assert response.context["abertura"] == abertura


@pytest.mark.django_db
class TestFechamentosPendentesView:
    """Tests for FechamentosPendentesView."""

    def test_list_pendentes_manager(self, client_logged, user, abertura):
        """Manager should see pending closures."""
        user.pode_aprovar_fechamento = True
        user.save()

        # Create a pending fechamento manually
        abertura.caixa.status = StatusCaixa.FECHADO
        abertura.caixa.save()

        fechamento = FechamentoCaixa.objects.create(
            tenant=abertura.tenant,
            abertura=abertura,
            operador=abertura.operador,
            saldo_sistema=Decimal("100.00"),
            saldo_informado=Decimal("90.00"),
            diferenca=Decimal("-10.00"),
            status=StatusFechamento.PENDENTE,
        )

        url = reverse("caixa:fechamentos_pendentes")
        response = client_logged.get(url)
        assert response.status_code == 200
        assert fechamento in response.context["fechamentos"]

    def test_list_pendentes_forbidden(self, client_logged, user):
        """Regular user should not access."""
        user.pode_aprovar_fechamento = False
        user.save()

        url = reverse("caixa:fechamentos_pendentes")
        response = client_logged.get(url)
        assert response.status_code == 403


@pytest.mark.django_db
class TestAprovarFechamentoView:
    """Tests for AprovarFechamentoView."""

    def test_aprovar_fechamento_success(self, client_logged, user, abertura):
        """Manager should approve closure."""
        user.pode_aprovar_fechamento = True
        user.save()

        abertura.caixa.status = StatusCaixa.FECHADO
        abertura.caixa.save()

        fechamento = FechamentoCaixa.objects.create(
            tenant=abertura.tenant,
            abertura=abertura,
            operador=abertura.operador,
            saldo_sistema=Decimal("100.00"),
            saldo_informado=Decimal("90.00"),
            diferenca=Decimal("-10.00"),
            status=StatusFechamento.PENDENTE,
        )

        url = reverse("caixa:aprovar_fechamento", kwargs={"pk": fechamento.pk})
        data = {
            "action": "aprovar",
            "observacao_aprovador": "Ok",
        }
        response = client_logged.post(url, data)
        assert response.status_code == 302

        fechamento.refresh_from_db()
        assert fechamento.status == StatusFechamento.APROVADO
        assert fechamento.aprovador == user

    def test_rejeitar_fechamento_success(self, client_logged, user, abertura):
        """Manager should reject closure with justification."""
        user.pode_aprovar_fechamento = True
        user.save()

        abertura.caixa.status = StatusCaixa.FECHADO
        abertura.caixa.save()

        fechamento = FechamentoCaixa.objects.create(
            tenant=abertura.tenant,
            abertura=abertura,
            operador=abertura.operador,
            saldo_sistema=Decimal("100.00"),
            saldo_informado=Decimal("90.00"),
            diferenca=Decimal("-10.00"),
            status=StatusFechamento.PENDENTE,
        )

        url = reverse("caixa:aprovar_fechamento", kwargs={"pk": fechamento.pk})
        data = {
            "action": "rejeitar",
            "observacao_aprovador": "Errado",
        }
        response = client_logged.post(url, data)
        assert response.status_code == 302

        fechamento.refresh_from_db()
        assert fechamento.status == StatusFechamento.REJEITADO
        assert fechamento.observacao_aprovador == "Errado"


@pytest.mark.django_db
class TestNovoMovimentoExtra:
    """Extra tests for NovoMovimentoView."""

    def test_movimento_saida_decreases_balance(self, client_logged, abertura, forma_pagamento):
        """Saida should decrease cache balance."""
        caixa = abertura.caixa
        caixa.status = StatusCaixa.ABERTO
        caixa.saldo_atual = Decimal("100.00")
        caixa.save()

        url = reverse("caixa:novo_movimento", kwargs={"pk": abertura.pk})
        data = {
            "tipo": "SAIDA",
            "forma_pagamento": forma_pagamento.pk,
            "valor": "30,00",
            "descricao": "Pagamento teste",
        }
        with patch("caixa_nfse.caixa.models.timezone") as mock_tz:
            mock_tz.localdate.return_value = abertura.data_hora.date()
            mock_tz.now.return_value = abertura.data_hora
            response = client_logged.post(url, data)
            assert response.status_code == 302

        caixa.refresh_from_db()
        assert caixa.saldo_atual == Decimal("70.00")

    def test_block_retroactive_movement(self, client_logged, abertura):
        """Should block movement if not today."""
        from caixa_nfse.caixa.models import AberturaCaixa

        # Set abertura to yesterday in DB
        yesterday = timezone.now() - datetime.timedelta(days=1)
        AberturaCaixa.objects.filter(pk=abertura.pk).update(data_hora=yesterday)
        abertura.refresh_from_db()

        # Mock localdate to return a date different from abertura.data_hora.date()
        today = yesterday.date() + datetime.timedelta(days=1)

        url = reverse("caixa:novo_movimento", kwargs={"pk": abertura.pk})
        with patch("caixa_nfse.caixa.models.timezone") as mock_tz:
            mock_tz.localdate.return_value = today
            response = client_logged.get(url)
            assert response.status_code == 302
            assert response.url == reverse("caixa:lista_movimentos", kwargs={"pk": abertura.pk})

    def test_htmx_request_returns_partial(self, client_logged, abertura):
        """HTMX request should return partial template."""
        url = reverse("caixa:novo_movimento", kwargs={"pk": abertura.pk})
        with patch("caixa_nfse.caixa.models.timezone") as mock_tz:
            mock_tz.localdate.return_value = abertura.data_hora.date()
            mock_tz.now.return_value = abertura.data_hora
            response = client_logged.get(url, HTTP_HX_REQUEST="true")
            assert response.status_code == 200
            assert "caixa/partials/movimento_form.html" in [t.name for t in response.templates]


@pytest.mark.django_db
class TestFecharCaixaExtra:
    """Extra tests for FecharCaixaView."""

    def test_fechar_htmx_response(self, client_logged, abertura):
        """HTMX request should return partial."""
        caixa = abertura.caixa
        caixa.status = StatusCaixa.ABERTO
        caixa.save()

        url = reverse("caixa:fechar", kwargs={"pk": caixa.pk})
        response = client_logged.get(url, HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert "caixa/partials/fechar_caixa_form.html" in [t.name for t in response.templates]

    def test_fechar_com_diferenca(self, client_logged, abertura):
        """Should detect difference and require approval."""
        caixa = abertura.caixa
        caixa.status = StatusCaixa.ABERTO
        caixa.save()

        # System balance = 100.00 (saldo_abertura) + 0 movs = 100.00

        url = reverse("caixa:fechar", kwargs={"pk": caixa.pk})
        data = {
            "saldo_informado": "90,00",  # User counts 90 (Missing 10)
            "justificativa_diferenca": "Sumiu",
            "observacoes": "Teste",
        }
        response = client_logged.post(url, data)
        assert response.status_code == 302

        abertura.refresh_from_db()
        fechamento = abertura.fechamento
        # 90 (informado) - 100 (sistema) = -10
        assert fechamento.diferenca == Decimal("-10.00")
        assert fechamento.requer_aprovacao is True
        assert fechamento.status == StatusFechamento.PENDENTE

    def test_fechar_htmx_post_success(self, client_logged, abertura):
        """HTMX POST should return HX-Refresh."""
        caixa = abertura.caixa
        caixa.status = StatusCaixa.ABERTO
        caixa.save()

        url = reverse("caixa:fechar", kwargs={"pk": caixa.pk})
        data = {
            "saldo_informado": "100,00",
            "justificativa_diferenca": "",
            "observacoes": "HTMX",
        }
        response = client_logged.post(url, data, HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert response.headers["HX-Refresh"] == "true"


@pytest.mark.django_db
class TestCaixaDetailView:
    """Tests for CaixaDetailView."""

    def test_detail_view(self, client_logged, caixa):
        """Should show caixa details."""
        url = reverse("caixa:detail", kwargs={"pk": caixa.pk})
        response = client_logged.get(url)
        assert response.status_code == 200
        assert response.context["object"] == caixa
        assert "abertura_atual" in response.context


@pytest.mark.django_db
class TestCaixaCreateViewExtra:
    """Extra tests for CaixaCreateView."""

    def test_create_caixa_context(self, client_logged, user):
        """Should have correct context on GET."""
        user.pode_aprovar_fechamento = True
        user.save()
        url = reverse("caixa:criar")
        response = client_logged.get(url)
        assert response.status_code == 200
        assert response.context["page_title"] == "Novo Caixa"


@pytest.mark.django_db
class TestAbrirCaixaExtra:
    """Extra tests for AbrirCaixaView."""

    def test_abrir_htmx_post_success(self, client_logged, caixa):
        """HTMX POST should return HX-Refresh."""
        # Ensure caixa is FECHADO
        caixa.status = StatusCaixa.FECHADO
        caixa.save()

        url = reverse("caixa:abrir", kwargs={"pk": caixa.pk})
        data = {
            "saldo_abertura": "100,00",
            "fundo_troco": "50,00",
            "observacao": "HTMX Open",
        }
        response = client_logged.post(url, data, HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert response.headers["HX-Refresh"] == "true"

        caixa.refresh_from_db()
        assert caixa.status == StatusCaixa.ABERTO

    def test_abrir_htmx_get_partial(self, client_logged, caixa):
        """HTMX GET should return partial."""
        url = reverse("caixa:abrir", kwargs={"pk": caixa.pk})
        response = client_logged.get(url, HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert "caixa/partials/abrir_caixa_form.html" in [t.name for t in response.templates]


@pytest.mark.django_db
class TestNovoMovimentoHTMX:
    """HTMX tests for NovoMovimento."""

    def test_movimento_htmx_post_success(self, client_logged, abertura, forma_pagamento):
        """HTMX POST should return HX-Refresh."""
        url = reverse("caixa:novo_movimento", kwargs={"pk": abertura.pk})
        data = {
            "tipo": "ENTRADA",
            "forma_pagamento": forma_pagamento.pk,
            "valor": "10,00",
            "descricao": "HTMX Mov",
        }
        with patch("caixa_nfse.caixa.models.timezone") as mock_tz:
            mock_tz.localdate.return_value = abertura.data_hora.date()
            mock_tz.now.return_value = abertura.data_hora
            response = client_logged.post(url, data, HTTP_HX_REQUEST="true")
            assert response.status_code == 200
            assert response.headers["HX-Refresh"] == "true"


@pytest.mark.django_db
class TestCoverageGapView:
    """Tests to close final coverage gaps."""

    def test_tenant_mixin_no_tenant(self, client_logged, user):
        """User with no tenant should be redirected."""
        user.tenant = None
        user.save()
        url = reverse("caixa:list")
        response = client_logged.get(url)
        # CaixaListView.dispatch redirects non-gerentes; no tenant = redirect to dashboard
        assert response.status_code == 302

    def test_fechar_caixa_permission_denied(self, client_logged, user, caixa):
        """User without permission should be denied."""
        user.pode_operar_caixa = False
        user.save()
        url = reverse("caixa:fechar", kwargs={"pk": caixa.pk})
        response = client_logged.get(url)
        assert response.status_code == 403

    def test_fechar_caixa_manager_other_operator(self, client_logged, user, abertura):
        """Manager closing another operator's register."""
        # Setup: abertura belongs to another user
        from caixa_nfse.core.models import User

        other_user = User.objects.create_user(
            email="other@test.com", password="123", tenant=user.tenant, pode_operar_caixa=True
        )
        abertura.operador = other_user
        abertura.save()
        abertura.caixa.operador_atual = other_user
        abertura.caixa.save()

        # Current user is manager
        user.pode_aprovar_fechamento = True
        user.save()

        url = reverse("caixa:fechar", kwargs={"pk": abertura.caixa.pk})
        response = client_logged.get(url)
        assert response.status_code == 200
        assert response.context["fechando_outro_operador"] is True
        assert response.context["operador_original"] == other_user

    def test_fechar_caixa_post_no_abertura(self, client_logged, caixa):
        """Should return 403 when no open abertura exists (test_func returns False)."""
        caixa.status = StatusCaixa.FECHADO
        caixa.save()
        caixa.aberturas.update(fechado=True)

        url = reverse("caixa:fechar", kwargs={"pk": caixa.pk})
        data = {
            "saldo_informado": "100,00",
            "justificativa_diferenca": "",
            "observacoes": "Fail",
        }
        response = client_logged.post(url, data)
        assert response.status_code == 403

    def test_rejeitar_fechamento_sem_justificativa(self, client_logged, user, abertura):
        """Should show error if rejecting without justification."""
        user.pode_aprovar_fechamento = True
        user.save()

        abertura.caixa.status = StatusCaixa.FECHADO
        abertura.caixa.save()

        fechamento = FechamentoCaixa.objects.create(
            tenant=abertura.tenant,
            abertura=abertura,
            operador=abertura.operador,
            saldo_sistema=Decimal("100.00"),
            saldo_informado=Decimal("90.00"),
            diferenca=Decimal("-10.00"),
            status=StatusFechamento.PENDENTE,
        )

        url = reverse("caixa:aprovar_fechamento", kwargs={"pk": fechamento.pk})
        data = {
            "action": "rejeitar",
            "observacao_aprovador": "",  # Empty
        }
        response = client_logged.post(url, data)
        assert response.status_code == 200  # Re-renders form
        messages_list = list(response.context["messages"])
        assert len(messages_list) > 0
        assert "Justificativa obrigatória" in str(messages_list[0])

    def test_novo_movimento_retroactive_htmx(self, client_logged, abertura):
        """Should return 403 Forbidden for retroactive movement via HTMX."""
        from caixa_nfse.caixa.models import AberturaCaixa

        yesterday = timezone.now() - datetime.timedelta(days=1)
        AberturaCaixa.objects.filter(pk=abertura.pk).update(data_hora=yesterday)
        abertura.refresh_from_db()

        today = yesterday.date() + datetime.timedelta(days=1)

        url = reverse("caixa:novo_movimento", kwargs={"pk": abertura.pk})
        with patch("caixa_nfse.caixa.models.timezone") as mock_tz:
            mock_tz.localdate.return_value = today
            response = client_logged.get(url, HTTP_HX_REQUEST="true")
            assert response.status_code == 403


@pytest.mark.django_db
class TestCoverageFinal:
    """Tests to extract the last drops of coverage."""

    def test_fechar_caixa_access_denied_for_non_opener_non_manager(
        self, client_logged, user, abertura
    ):
        """Operator (not opener, not manager) cannot close."""
        # Setup: abertura belongs to another user
        from caixa_nfse.core.models import User

        other_user = User.objects.create_user(
            email="owner@test.com", password="123", tenant=user.tenant, pode_operar_caixa=True
        )
        abertura.operador = other_user
        abertura.save()

        # Current user has permission to operate, but NOT manager, NOT owner
        user.pode_operar_caixa = True
        user.pode_aprovar_fechamento = False
        user.save()

        url = reverse("caixa:fechar", kwargs={"pk": abertura.caixa.pk})
        response = client_logged.get(url)
        assert response.status_code == 403

    def test_calcular_detalhamento_loop(self, client_logged, abertura, forma_pagamento):
        """Ensure detailment loop runs with movements."""
        from caixa_nfse.caixa.models import MovimentoCaixa, TipoMovimento

        # Add movements
        MovimentoCaixa.objects.create(
            tenant=abertura.tenant,
            abertura=abertura,
            tipo=TipoMovimento.ENTRADA,
            forma_pagamento=forma_pagamento,
            valor=Decimal("100.00"),
        )
        MovimentoCaixa.objects.create(
            tenant=abertura.tenant,
            abertura=abertura,
            tipo=TipoMovimento.SAIDA,
            forma_pagamento=forma_pagamento,
            valor=Decimal("50.00"),
        )

        # Close box
        abertura.caixa.status = StatusCaixa.ABERTO
        abertura.caixa.save()

        url = reverse("caixa:fechar", kwargs={"pk": abertura.caixa.pk})
        data = {
            "saldo_informado": "150,00",  # 100 + 100 - 50 = 150
            "observacoes": "Loop Test",
        }
        response = client_logged.post(url, data)
        assert response.status_code == 302

        abertura.refresh_from_db()
        det = abertura.fechamento.detalhamento
        assert forma_pagamento.nome in det
        assert det[forma_pagamento.nome]["entradas"] == 100.0
        assert det[forma_pagamento.nome]["saidas"] == 50.0

    def test_fechar_caixa_post_race_condition(self, client_logged, user, abertura):
        """Simulate closure post when opening is gone (race)."""
        abertura.caixa.status = StatusCaixa.ABERTO
        abertura.caixa.save()

        url = reverse("caixa:fechar", kwargs={"pk": abertura.caixa.pk})

        # Delete abertura before post — test_func will return False (no open abertura)
        abertura.delete()

        data = {"saldo_informado": "0,00"}
        response = client_logged.post(url, data)
        assert response.status_code == 403  # No open abertura = permission denied
