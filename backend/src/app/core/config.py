"""Settings from environment variables (and a local .env file). No secret has a default."""

import logging
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class SettingsError(ValueError):
    """The configuration is unsafe or incomplete, so the service must not start."""


class Settings(BaseSettings):
    # The root .env is used when running from backend/, a local .env when running from the root.
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    env: Literal["local", "prod"] = "local"
    database_url: str | None = None

    # The writer login is an explicit switch, never an implicit fallback.
    basic_auth_enabled: bool = False
    basic_auth_user: str = ""
    basic_auth_password: SecretStr = SecretStr("")

    # Optional extra (AI draft generation): off unless explicitly switched on. The key comes from
    # the environment only. The limits keep the cost and the load small.
    ai_enabled: bool = False
    anthropic_api_key: SecretStr = SecretStr("")
    anthropic_model: str = "claude-sonnet-4-6"
    ai_max_output_tokens: int = 3000
    ai_requests_per_minute: int = 5

    @model_validator(mode="after")
    def _check_authentication(self) -> "Settings":
        if self.env == "prod" and not self.basic_auth_enabled:
            raise SettingsError("BASIC_AUTH_ENABLED must be true when ENV is prod")
        if self.basic_auth_enabled and (
            not self.basic_auth_user or not self.basic_auth_password.get_secret_value()
        ):
            raise SettingsError(
                "BASIC_AUTH_USER and BASIC_AUTH_PASSWORD must both be set "
                "when BASIC_AUTH_ENABLED is true"
            )
        if self.ai_enabled and not self.anthropic_api_key.get_secret_value():
            raise SettingsError("ANTHROPIC_API_KEY must be set when AI_ENABLED is true")
        return self

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"


def warn_if_authentication_is_off(settings: Settings) -> None:
    if not settings.basic_auth_enabled:
        logger.warning(
            "BASIC_AUTH_ENABLED is false: the writer API is open. Use this for local work only."
        )


def load_settings() -> Settings:
    return Settings()
