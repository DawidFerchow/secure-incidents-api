import pytest

from app.core.settings import Settings


def test_environment_settings_enforce_minimum_seed_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEED_RECORDS", "10")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setenv("ALLOWED_HOSTS", "localhost, example.internal")

    settings = Settings.from_env()

    assert settings.seed_records == 2_000
    assert settings.log_level == "DEBUG"
    assert settings.allowed_hosts == ("localhost", "example.internal")
