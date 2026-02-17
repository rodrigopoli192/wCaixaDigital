"""
Tests for NFSeForm.clean_competencia (YYYY-MM → date conversion).
"""

import datetime

from caixa_nfse.nfse.forms import NFSeForm


class TestCleanCompetencia:
    """Exercise the YYYY-MM conversion path in clean_competencia."""

    def _call_clean_competencia(self, raw_value):
        """Instantiate form and call clean_competencia directly to isolate from other fields."""
        form = NFSeForm(data={"competencia": raw_value})
        # Manually populate cleaned_data for the field we care about
        form.cleaned_data = {"competencia": None}
        form.data = {"competencia": raw_value}
        return form.clean_competencia()

    def test_yyyy_mm_converted_to_date(self):
        """type=month sends '2026-03' which must become date(2026, 3, 1)."""
        result = self._call_clean_competencia("2026-03")
        assert result == datetime.date(2026, 3, 1)

    def test_date_value_passed_through(self):
        """If already a date in cleaned_data, returns unchanged."""
        form = NFSeForm(data={"competencia": "2026-03-01"})
        form.cleaned_data = {"competencia": datetime.date(2026, 3, 1)}
        form.data = {"competencia": "2026-03-01"}
        result = form.clean_competencia()
        assert result == datetime.date(2026, 3, 1)

    def test_invalid_yyyy_mm_falls_through(self):
        """Invalid month like '2026-99' should not crash."""
        result = self._call_clean_competencia("2026-99")
        assert result is None  # Falls through to returning cleaned_data value

    def test_empty_competencia(self):
        """Empty competencia returns None without crash."""
        result = self._call_clean_competencia("")
        assert result is None

    def test_short_string_skipped(self):
        """Strings shorter than 7 chars skip the YYYY-MM path."""
        result = self._call_clean_competencia("2026")
        assert result is None
