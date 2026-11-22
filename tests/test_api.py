import pytest

from src.api.main import health
from src.api.schemas import AlertInput


def test_health():
    assert health()["status"] == "ok"


def test_alert_rejects_extra_fields():
    with pytest.raises(ValueError):
        AlertInput.model_validate({"service": "checkout-api", "summary": "5xx", "extra": True})
