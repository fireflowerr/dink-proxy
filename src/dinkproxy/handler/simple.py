from dinkproxy.types import DinkHandler

def _handler(payload: dict) -> dict:
    """
    Simple handler.

    :param payload: incoming payload
    :return: incoming payload
    """
    return payload


handler: DinkHandler = _handler
