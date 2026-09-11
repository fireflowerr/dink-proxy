from dinkproxy.types import DinkHandler
from dinkproxy.config import get_config

def _handler(payload: dict) -> dict:
    """
    Applies default styling to dink embeds.

    :param payload: incoming payload
    :return: default stylized payload
    """
    embeds: list[dict] = payload.get('embeds', [])
    for embed in embeds:
        embed['color'] = get_config().color
        del embed['footer']
        del embed['timestamp']

    return payload


handler: DinkHandler = _handler
