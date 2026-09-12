from dinkproxy.config import get_config
from dinkproxy.types import DinkHandler
from dinkproxy.util.colors import set_colors


def _handler(payload: dict) -> dict | None:
    config = get_config()
    if not payload.get('playerName') in config.group.allowlist:
        return None

    set_colors(payload.get('embeds', []), config.group.color)

    return payload


handler: DinkHandler = _handler
