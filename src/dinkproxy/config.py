import tomllib
import logging
from pathlib import Path
from pydantic import BaseModel, Field


log = logging.getLogger(__name__)


from enum import Enum, auto

class Deployment(Enum):
    DEV = 'dev'
    PROD = 'prod'


class _CommonConfig(BaseModel):
    color: int = Field(default=0)


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
    complex_timeout : int = Field(default=30)
    worker_timeout: int = Field(default=33)


class Config(_CommonConfig):
    loot: LootConfig = Field(default_factory=LootConfig)
    group: GroupConfig = Field(default_factory=GroupConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)

    @staticmethod
    def load(config_path: str) -> Config:
        with open(config_path, 'rb') as handle:
            data = tomllib.load(handle)
            return Config.model_validate(data)


config: Config | None = None


def get_config() -> Config:
    global config
    if config is None:
        path = Path('config.toml')
        if path.exists():
            config = Config.load('config.toml')
        else:
            log.warning(f'config.toml not found, using default config')
            config = Config()

    return config
