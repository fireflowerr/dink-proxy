from dinkproxy.config import get_config
from dinkproxy.types import DinkHandler
from dinkproxy.util.colors import set_color


def _handler(payload: dict) -> dict:
    """
    Applies default styling to dink embeds.

    :param payload: incoming payload
    :return: default stylized payload
    """
    embeds: list[dict] = payload.get('embeds', [])
    for embed in embeds:
        set_color(embed, get_config().color)
        del embed['footer']
        del embed['timestamp']

    return payload


handler: DinkHandler = _handler
