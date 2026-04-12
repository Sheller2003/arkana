# Deploy

Dieses Projekt kann als API-Container deployed werden. Die Sandbox-Sessions laufen weiter als separate Docker-Container auf dem Host.

## Voraussetzungen

- Docker und Docker Compose auf dem Server
- erreichbare MySQL-Datenbank
- `.env` im Projektordner
- API-Basic-Auth-Passwort in `.env`, wenn kein Keyring im Container vorhanden ist

## Wichtige Architektur

- `arkana-api` ist der eigentliche API-Container
- Python- und R-Sessions werden zur Laufzeit vom API-Container aus ueber den Host-Docker-Daemon gestartet
- dafuer wird `/var/run/docker.sock` in den API-Container gemountet
- `keyring` speichert Passwoerter im Container dateibasiert und persistent unter `./keyring_data`

## Start

```bash
docker compose up -d --build
```

## Keyring im Container

Der Container verwendet absichtlich einen dateibasierten Keyring-Backend:

- Backend: `keyrings.alt.file.PlaintextKeyring`
- persistenter Ordner: `./keyring_data`

Dadurch funktionieren `keyring.get_password(...)` und `keyring.set_password(...)` auch auf dem Server fuer alle User.

Wenn du API-Passwoerter initial setzen willst, kannst du z. B. im laufenden Container dein vorhandenes Script verwenden:

```bash
docker compose exec arkana-api python scripts/cli_set_api_pw.py
```

Der `.env`-Fallback fuer `ARKANA_API_PASSWORD` bzw. `ARKANA_API_PASSWORD_<USER>` bleibt nur als Reserve aktiv.

## Stop

```bash
docker compose down
```

## Update

```bash
git pull
docker compose up -d --build
```

## GitHub Pipeline

Es gibt eine GitHub-Action unter [`.github/workflows/deploy.yml`](/Users/sheller2003/PycharmProjects/arkanaMDD/.github/workflows/deploy.yml:1).

Sie macht bei Push auf `main`:

```bash
rsync -> Server
docker compose up -d --build
```

Benötigte GitHub-Secrets:

- `DEPLOY_HOST`
- `DEPLOY_PORT`
- `DEPLOY_USER`
- `DEPLOY_PATH`
- `DEPLOY_SSH_KEY`

Wichtig:

- `.env` wird bewusst nicht aus Git synchronisiert und muss bereits auf dem Server liegen
- `arkana_spheres/` und `keyring_data/` bleiben auf dem Server persistent und werden nicht überschrieben

## Dateien und Sessions

- persistenter Workspace: `./arkana_spheres`
- API-Port: `${ARKANA_API_PORT:-8000}`

## Wichtige Hinweise

- `ROOT_PATH` in `.env` sollte auf die oeffentliche Server-URL zeigen, z. B. `https://example.com`
- der API-Container braucht Zugriff auf den Host-Docker-Daemon, sonst funktionieren `arkana_sphere`-Sessions nicht
- benoetigte Runtime-Images wie `python:3.11-slim` oder `r-base:latest` muessen auf dem Host verfuegbar sein
