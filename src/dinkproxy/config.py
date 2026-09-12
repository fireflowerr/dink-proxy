import logging
import tomllib
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, ValidationError

log = logging.getLogger(__name__)


from enum import Enum


class Deployment(Enum):
    DEV = 'dev'
    PROD = 'prod'


def _coerce_log_level(value: object) -> object:
    """
    Accepts a log level name ('DEBUG', 'debug') as well as its numeric value.
    """
    if isinstance(value, str):
        level = logging.getLevelNamesMapping().get(value.upper())
        if level is None:
            raise ValueError(f'unknown log level: {value!r}')
        return level

    return value


LogLevel = Annotated[int, BeforeValidator(_coerce_log_level)]


class _CommonConfig(BaseModel):
    color: int | None = Field(default=None)


class LootConfig(_CommonConfig):
    min_value: int = Field(default=0)
    min_rarity: float = Field(default=0)


class GroupConfig(_CommonConfig):
    allowlist: list[str] = Field(default=[])


class ServerConfig(BaseModel):
    host: str = Field(default='0.0.0.0')
    port: int = Field(default=5000)
    deployment: Deployment = Field(default=Deployment.PROD)
    workers: int = Field(default=2)
    threads: int = Field(default=4)
    simple_timeout: int = Field(default=10)
    complex_timeout: int = Field(default=30)
    worker_timeout: int = Field(default=33)


class Config(_CommonConfig):
    loot: LootConfig = Field(default_factory=LootConfig)
    group: GroupConfig = Field(default_factory=GroupConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    log_level: LogLevel = Field(default=logging.INFO)

    @staticmethod
    def load(config_path: str) -> Config:
        with open(config_path, 'rb') as handle:
            data = tomllib.load(handle)
            try:
                return Config.model_validate(data, extra='forbid')
            except ValidationError as exc:
                # Booting on defaults would silently change what gets forwarded, so an
                # invalid config is fatal rather than a fallback.
                log.critical('Invalid config.toml: %s', exc)
                raise SystemExit(1) from exc


config: Config | None = None


def get_config() -> Config:
    global config
    if config is None:
        path = Path('config.toml')
        if path.exists():
            config = Config.load('config.toml')
        else:
            log.warning('config.toml not found, using default config')
            config = Config()

    return config
