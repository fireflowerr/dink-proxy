import logging

from dinkproxy.types import DinkHandler, DinkType

log = logging.getLogger(__name__)


class DinkApp:
    def __init__(self):
        self._handlers: list[tuple[DinkHandler, list[str] | None]] = []

    def register(self, handler: DinkHandler, notifications: list[DinkType] | None = None) -> None:
        """
        Registers a dink handler. If the notification list is empty it will apply to all incoming requests.
        Handlers are invoked in order of registration.

        :param handler:
        :param notifications:
        :return: none
        """
        str_notifications = None if notifications is None else [notification.name for notification in notifications]
        self._handlers.append((handler, str_notifications))

    def handle(self, payload: dict) -> dict | None:
        """
        Applies each applicable handler to the given payload and returns the result.

        :param payload: parsed incoming payload
        :return: outgoing payload, or None when a handler dropped it
        """
        notification_type = payload.get('type')
        for index, registration in enumerate(self._handlers):
            handler, notifications = registration
            # noinspection broad-exception
            try:
                if notifications is None or notification_type in notifications:
                    # noinspection bad-argument-type
                    payload = handler(payload)

                    if payload is None:
                        log.debug('payload rejected [handlerIdx: %d]', index)
                        return None

            except Exception:
                log.exception('failed to handle payload [handlerIdx: %d]', index)

        return payload
