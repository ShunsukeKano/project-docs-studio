"""The suite never sees a developer's real AI settings."""

import os

from app.core.config import Settings


def test_a_local_env_file_cannot_switch_ai_on_for_the_tests() -> None:
    settings = Settings(env="local")
    assert settings.ai_enabled is False
    assert settings.anthropic_api_key.get_secret_value() == ""


def test_no_real_key_is_in_the_environment_during_tests() -> None:
    assert os.environ["ANTHROPIC_API_KEY"] == ""
