import json
import logging
import os

import requests

from dinkproxy.config import get_config, Deployment
from dinkproxy.types import DinkType
from dinkproxy.handler.loot import handler as loot_handler
from dinkproxy.handler.simple import handler as simple_handler
from dinkproxy.handler.style import handler as style_handler
from dinkproxy.handler.group_storage import handler as group_storage

from flask import jsonify, request, Flask

from dinkproxy.app import DinkApp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)

log = logging.getLogger(__name__)


app = DinkApp()
app.register(style_handler)
app.register(loot_handler, [DinkType.LOOT])
app.register(group_storage, [DinkType.GROUP_STORAGE])
app.register(simple_handler, [
    DinkType.ACHIEVEMENT_DIARY,
    DinkType.COLLECTION,
    DinkType.COMBAT_ACHIEVEMENT,
    DinkType.DEATH,
    DinkType.LEVEL,
])


server = Flask(__name__)

config = get_config()

@server.route('/heatlh', methods=['GET'])
def health():
    """
    Health check endpoint.
    :return: 200 ok
    """
    return jsonify({'status': 'ok'}), 200


def _incoming_payload() -> dict | None:
    """
    Parses the incoming webhook into its JSON payload.

    DinkPlugin posts multipart/form-data carrying a ``payload_json`` part when
    image sending is enabled, and a plain JSON body otherwise.

    :return: parsed payload, or None when the request carries none
    :raises ValueError: when the payload is not valid JSON
    """
    raw_payload = request.form.get('payload_json')
    if raw_payload is not None:
        return json.loads(raw_payload)

    return request.get_json(silent=True)


@server.route('/hook', methods=['POST'])
def hook():
    """
    Receives a dink webhook, runs it through the handler chain and forwards the
    result to the Discord webhook configured for its notification type.

    :return: 204 when a handler dropped it, 400 when the request carries no
             payload, 500 when no webhook is configured, 502 when Discord
             rejected it, 200 on success
    """
    try:
        payload = _incoming_payload()
    except ValueError:
        return jsonify({'error': 'payload_json is not valid JSON'}), 400

    if payload is None:
        return jsonify({'error': 'no JSON payload found in the request'}), 400

    outgoing = app.handle(payload)
    if outgoing is None:
        return '', 204

    notification_type = outgoing.get('type')
    target_url = os.environ.get(f'DINK_{notification_type}_HOOK') or os.environ.get('DINK_DEFAULT_HOOK')
    if target_url is None:
        log.error("No webhook configured for notification type %s", notification_type)
        return jsonify({'error': f'no webhook configured for type {notification_type}'}), 500

    global config
    server_config = config.server
    try:
        if request.files:
            response = requests.post(
                target_url,
                data={'payload_json': json.dumps(outgoing)},
                files=[
                    (field, (upload.filename, upload.stream, upload.mimetype))
                    for field, upload in request.files.items()
                ],
                timeout=server_config.complex_timeout,
            )
        else:
            response = requests.post(
                target_url,
                json=outgoing,
                timeout=server_config.simple_timeout,
            )
    except requests.RequestException as exc:
        log.exception("Could not forward the notification to Discord")
        return '', 502

    if response.status_code >= 400:
        log.error("Discord rejected the payload (%d): %s", response.status_code, response.text[:200])
        return jsonify({'error': 'discord rejected the payload', 'discord_status': response.status_code}), 502

    log.info("Forwarded %s notification to Discord (%d)", notification_type, response.status_code)
    return jsonify({'status': 'forwarded', 'discord_status': response.status_code}), 200


def _serve_with_gunicorn(flask_app) -> None:
    from gunicorn.app.base import BaseApplication
    global config

    options = {
        'bind': f'{config.server.host}:{config.server.port}',
        'threads': config.server.threads,
        'timeout': config.server.worker_timeout,
        'workers': config.server.workers,
    }

    log.info(
        "Starting dinkproxy on %s (workers=%d, threads=%d)",
        options['bind'], options['workers'], options['threads'],
    )

    class _Application(BaseApplication):
        def load_config(self) -> None:
            for key, value in options.items():
                if key in self.cfg.settings and value is not None:
                    self.cfg.set(key.lower(), value)

        def load(self):
            return flask_app

    _Application().run()


if __name__ == '__main__':
    global config
    if config.server.deployment == Deployment.PROD:
        _serve_with_gunicorn(server)
    else:
        log.info("Starting dinkproxy on %s", f'{config.server.host}:{config.server.port}')
        server.run(host=config.server.host, port=config.server.port)
