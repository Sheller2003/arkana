# Deploy

Dieses Projekt kann als API-Container deployed werden. Die Sandbox-Sessions laufen weiter als separate Docker-Container auf dem Host.

## Voraussetzungen

- Docker und Docker Compose auf dem Server
- erreichbare MySQL-Datenbank
- `.env` im Projektordner

## Wichtige Architektur

- `arkana-api` ist der eigentliche API-Container
- Python- und R-Sessions werden zur Laufzeit vom API-Container aus ueber den Host-Docker-Daemon gestartet
- dafuer wird `/var/run/docker.sock` in den API-Container gemountet

## Start

```bash
docker compose up -d --build
```

## Stop

```bash
docker compose down
```

## Update

```bash
git pull
docker compose up -d --build
```

## Dateien und Sessions

- persistenter Workspace: `./arkana_spheres`
- API-Port: `${ARKANA_API_PORT:-8000}`

## Wichtige Hinweise

- `ROOT_PATH` in `.env` sollte auf die oeffentliche Server-URL zeigen, z. B. `https://example.com`
- der API-Container braucht Zugriff auf den Host-Docker-Daemon, sonst funktionieren `arkana_sphere`-Sessions nicht
- benoetigte Runtime-Images wie `python:3.11-slim` oder `r-base:latest` muessen auf dem Host verfuegbar sein
