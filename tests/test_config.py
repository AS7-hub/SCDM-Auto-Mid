import os
import pytest
from pydantic import ValidationError
from scdm.core.config import Settings, AppMode

def test_default_config_loading():
    settings = Settings()
    assert settings.app_mode == AppMode.MOCK
    assert settings.gemini_model == "gemini-2.5-pro"
    assert settings.neo4j_uri == "bolt://127.0.0.1:7687"
    assert isinstance(settings.risk_thresholds, dict)
    assert settings.risk_thresholds["high"] == 0.8

def test_missing_required_config(monkeypatch):
    # Pydantic Settings allows fields with defaults to be omitted.
    # If we made a field required (without default), it would raise ValidationError.
    # Let's test overriding a value via env
    monkeypatch.setenv("APP_MODE", "LIVE")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
    
    settings = Settings()
    assert settings.app_mode == AppMode.LIVE
    assert settings.gemini_api_key == "test-key-123"

def test_invalid_enum_config(monkeypatch):
    monkeypatch.setenv("APP_MODE", "INVALID_MODE")
    with pytest.raises(ValidationError):
        Settings()
