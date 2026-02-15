"""Tests for structured logging: RequestContextFilter and RequestLoggingMiddleware."""

import json
import logging

import pytest
from django.test import Client, RequestFactory

from caixa_nfse.core.logging_filters import (
    RequestContextFilter,
    clear_request_context,
    set_request_context,
)
from caixa_nfse.core.logging_middleware import RequestLoggingMiddleware
from caixa_nfse.tests.factories import TenantFactory, UserFactory


class TestRequestContextFilter:
    def test_adds_default_fields_without_context(self):
        f = RequestContextFilter()
        record = logging.LogRecord("test", logging.INFO, "", 0, "msg", (), None)
        clear_request_context()
        f.filter(record)
        assert record.request_id == "-"
        assert record.tenant_id == "-"
        assert record.user_id == "-"

    def test_adds_fields_from_context(self):
        f = RequestContextFilter()
        set_request_context(request_id="abc123", user_id="42", tenant_id="t-99")
        record = logging.LogRecord("test", logging.INFO, "", 0, "msg", (), None)
        f.filter(record)
        assert record.request_id == "abc123"
        assert record.user_id == "42"
        assert record.tenant_id == "t-99"
        clear_request_context()

    def test_clear_resets_fields(self):
        set_request_context(request_id="x", user_id="y", tenant_id="z")
        clear_request_context()
        f = RequestContextFilter()
        record = logging.LogRecord("test", logging.INFO, "", 0, "msg", (), None)
        f.filter(record)
        assert record.request_id == "-"


@pytest.mark.django_db
class TestRequestLoggingMiddleware:
    def test_sets_x_request_id_header(self):
        tenant = TenantFactory()
        user = UserFactory(tenant=tenant)
        client = Client()
        client.force_login(user)
        response = client.get("/login/")
        assert "X-Request-ID" in response
        assert len(response["X-Request-ID"]) == 8

    def test_anonymous_user_gets_request_id(self):
        client = Client()
        response = client.get("/login/")
        assert "X-Request-ID" in response

    def test_middleware_callable(self):
        factory = RequestFactory()
        request = factory.get("/")

        from django.contrib.auth.models import AnonymousUser

        request.user = AnonymousUser()

        def dummy_response(req):
            from django.http import HttpResponse

            return HttpResponse("ok")

        mw = RequestLoggingMiddleware(dummy_response)
        response = mw(request)
        assert response["X-Request-ID"]
        assert response.status_code == 200


class TestJsonFormatterIntegration:
    def test_json_output_is_valid(self):
        """Verify the JSON formatter produces valid JSON with expected fields."""
        from pythonjsonlogger.json import JsonFormatter

        formatter = JsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
        )
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)

        # Add a filter to inject context fields
        f = RequestContextFilter()
        handler.addFilter(f)
        set_request_context(request_id="test123", user_id="u1", tenant_id="t1")

        logger = logging.getLogger("test.json.output")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        import io

        stream = io.StringIO()
        handler.stream = stream

        logger.info("Test message")

        output = stream.getvalue().strip()
        data = json.loads(output)

        assert data["level"] == "INFO"
        assert data["logger"] == "test.json.output"
        assert data["message"] == "Test message"
        assert data["request_id"] == "test123"
        assert data["tenant_id"] == "t1"

        logger.removeHandler(handler)
        clear_request_context()
