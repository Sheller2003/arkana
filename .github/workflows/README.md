# GitHub Deploy Pipeline

Diese Pipeline synchronisiert bei jedem Push auf `main` den Projektstand per `rsync` auf den Server und startet dort:

```bash
docker compose -f docker-compose.yml -f docker-compose.server.yml up -d --build
```

Die Basisdatei `docker-compose.yml` bleibt für den bestehenden Direktzugriff auf `:8000`.
Die server-spezifische Datei `docker-compose.server.yml` ergänzt nur Traefik/HTTPS über `arkanan8n.cloud`.

## Benötigte GitHub Secrets

- `DEPLOY_HOST`
- `DEPLOY_PORT`
- `DEPLOY_USER`
- `DEPLOY_PATH`
- `DEPLOY_SSH_KEY`
- `DEPLOY_KNOWN_HOST`

`DEPLOY_KNOWN_HOST` sollte die feste Host-Key-Zeile des Servers enthalten, z. B.:

```text
72.61.87.45 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIA5wkuLUBA5Bc4KQLRChllUpDcWtsMhb2rh4YJpJIS1E
```

## Server-Voraussetzungen

- Zielordner aus `DEPLOY_PATH` existiert oder ist vom User beschreibbar
- `.env` liegt bereits auf dem Server im Zielordner
- Docker und Docker Compose sind installiert
- der SSH-User darf `docker compose` ausführen
- das externe Docker-Netz `root_default` existiert bereits auf dem Server
- die Domain `arkanan8n.cloud` zeigt auf den Server und der Traefik-Resolver `mytlschallenge` ist konfiguriert

## Zugriff

Nach dem Deploy bleiben beide Wege parallel aktiv:

- Direktzugriff: `http://<server-ip>:8000`
- HTTPS über Traefik: `https://arkanan8n.cloud`
