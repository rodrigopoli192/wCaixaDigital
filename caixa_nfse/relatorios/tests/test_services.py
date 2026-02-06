from decimal import Decimal
from unittest.mock import patch

import pytest

from caixa_nfse.relatorios.services import ExportService, format_currency


@pytest.fixture
def mock_data():
    return {
        "title": "Test Report",
        "columns": [
            {"key": "name", "label": "Name", "align": "left"},
            {"key": "value", "label": "Value", "align": "right"},
        ],
        "rows": [
            {"name": "Item 1", "value": 10.0},
            {"name": "Item 2", "value": Decimal("20.50")},
        ],
        "totals": {"value": 30.50},
        "filters": {"Date": "2023-01-01"},
        "tenant_name": "Test Tenant",
    }


class TestFormatCurrency:
    def test_format_currency_none(self):
        assert format_currency(None) == "R$ 0,00"

    def test_format_currency_float(self):
        assert format_currency(1234.56) == "R$ 1.234,56"

    def test_format_currency_decimal(self):
        assert format_currency(Decimal("1234.56")) == "R$ 1.234,56"


class TestExportServicePDF:
    @patch("caixa_nfse.relatorios.services.HAS_WEASYPRINT", False)
    def test_to_pdf_missing_dependency(self, mock_data):
        response = ExportService.to_pdf(**mock_data)
        assert response.status_code == 500
        assert b"WeasyPrint" in response.content

    @patch("caixa_nfse.relatorios.services.HAS_WEASYPRINT", True)
    @patch("caixa_nfse.relatorios.services.render_to_string")
    @patch("caixa_nfse.relatorios.services.HTML")
    def test_to_pdf_success(self, mock_html, mock_render, mock_data):
        # Setup mocks
        mock_render.return_value = "<html></html>"
        mock_html_instance = mock_html.return_value
        mock_html_instance.write_pdf.return_value = b"pdf_content"

        response = ExportService.to_pdf(**mock_data)

        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"
        assert response["Content-Disposition"].startswith("attachment; filename=")
        assert response.content == b"pdf_content"

        # Verify Context
        mock_render.assert_called_once()
        context = mock_render.call_args[0][1]
        assert context["title"] == "Test Report"
        assert context["rows"] == mock_data["rows"]


class TestExportServiceXLSX:
    @patch("caixa_nfse.relatorios.services.HAS_OPENPYXL", False)
    def test_to_xlsx_missing_dependency(self, mock_data):
        # Remove tenant_name as it's not in to_xlsx signature
        data = mock_data.copy()
        del data["tenant_name"]

        response = ExportService.to_xlsx(**data)
        assert response.status_code == 500
        assert b"openpyxl" in response.content

    @patch("caixa_nfse.relatorios.services.HAS_OPENPYXL", True)
    def test_to_xlsx_success(self, mock_data):
        # Remove tenant_name as it's not in to_xlsx signature
        data = mock_data.copy()
        del data["tenant_name"]

        response = ExportService.to_xlsx(**data)

        assert response.status_code == 200
        assert (
            response["Content-Type"]
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert response["Content-Disposition"].startswith("attachment; filename=")
        # Content validation would require loading the excel file,
        # but basic response check is robust enough for now
