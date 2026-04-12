# GitHub Deploy Pipeline

Diese Pipeline synchronisiert bei jedem Push auf `main` den Projektstand per `rsync` auf den Server und startet dort:

```bash
docker compose up -d --build
```

## Benötigte GitHub Secrets

- `DEPLOY_HOST`
- `DEPLOY_PORT`
- `DEPLOY_USER`
- `DEPLOY_PATH`
- `DEPLOY_SSH_KEY`

## Server-Voraussetzungen

- Zielordner aus `DEPLOY_PATH` existiert oder ist vom User beschreibbar
- `.env` liegt bereits auf dem Server im Zielordner
- Docker und Docker Compose sind installiert
- der SSH-User darf `docker compose` ausführen
