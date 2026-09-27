from dinkproxy.config import get_config
from dinkproxy.types import DinkHandler
from dinkproxy.util.colors import set_colors


def _handler(payload: dict) -> dict | None:
    """
    Filters level notifications testing by every_10, every_5, and every_1.

    :param payload: incoming payload
    :return: filtered payload
    """
    levelled_skills = payload.get('extra', {}).get('levelledSkills')

    if levelled_skills is None:
        return None

    config = get_config().level

    # list of (threshold, divisor)
    divisors: list[tuple[int, int]] = []

    if config.every_10 is not None:
        divisors.append((config.every_10, 10))

    if config.every_5 is not None:
        divisors.append((config.every_5, 5))

    if config.every_1 is not None:
        divisors.append((config.every_1, 1))

    for level in levelled_skills.values():
        for threshold, divisor in divisors:
            if level >= threshold and level % divisor == 0:
                set_colors(payload.get('embeds', []), config.color)
                return payload

    return None


handler: DinkHandler = _handler
