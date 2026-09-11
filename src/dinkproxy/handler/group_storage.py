from dinkproxy.types import DinkHandler
from dinkproxy.config import get_config


def _handler(payload: dict) -> dict | None:
    config = get_config()
    if payload.get('playerName') in config.group.allowlist:
        return payload
    else:
        return None


handler: DinkHandler = _handler
