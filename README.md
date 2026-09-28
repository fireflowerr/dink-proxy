# dink-proxy

Forwards OSRS Dink notifications to Discord webhooks.

## Setup

Templates for both runtime files live in `defaults/`. Copy them into the project
root before the first run:

```sh
cp ./defaults/* .
```

This **overwrites** `config.toml` and `.env` so be careful to only run it on initial install.

## Configuration

`config.toml` controls behavior, log level, embed colors, and which loot,
group storage, and level-up events get forwarded. Every setting is optional and
the file documents the built-in defaults; uncomment a line to override it.

`.env` configures notification channels: `DINK_DEFAULT_HOOK` is the webhook URL
used by default, and any `DINK_<TYPE>_HOOK` overrides it per notification type.

## Run

```sh
docker compose up -d --build
```

`docker compose logs -f` to follow along. Docker Compose reads both files when
it creates the service, so if the container starts without your changes, run
`docker compose up -d --force-recreate`.
