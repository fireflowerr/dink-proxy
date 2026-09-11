from urllib import parse
from dinkproxy.types import DinkHandler
from dinkproxy.config import get_config

def _handler(payload: dict) -> dict | None:
    """
    Handles loot notification types.

    :param payload: payload
    :return: formatted payload or none if criteria unmet
    """
    config = get_config()
    extra = payload.get('extra', {})
    items = extra.get('items', [])
    description = ''

    should_send: bool = False
    for item in items:
        name = item['name']
        raw_link = 'https://oldschool.runescape.wiki/w/Special:Search?' + parse.urlencode({'search': name})
        link = f'[{name}]({raw_link})'
        quantity = item.get('quantity', 1)
        value = item.get('priceEach')
        rarity = item.get('rarity')

        if value is not None and value >= config.loot.min_value:
            should_send = True
            pretty_value = f'{value:,}'
            description += f'• {quantity} x {link} ({pretty_value})\n'

        if not should_send and rarity is not None and float(rarity) <= config.loot.min_rarity:
            should_send = True

    if not should_send:
        return None

    embeds: list[dict] = payload.get('embeds', [])
    embed = embeds[0]
    embed['description'] = description
    del embed['fields']

    return payload


handler: DinkHandler = _handler
