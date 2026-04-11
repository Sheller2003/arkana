# API Services

## Überblick

Diese Datei beschreibt die aktuell definierten API-Services für das DB-Management von `arkanaMDD`.

## Service-Tabelle

| Methode | Pfad | Zweck | Berechtigung | Request-Parameter | Response |
|---|---|---|---|---|---|
| `GET` | `/db/<db_id>/` | Liefert allgemeine Informationen zu einer registrierten Datenbank. | `company_admin` | Path: `db_id:int` | JSON mit DB-Metadaten ohne Passwörter und ohne `personal_user` |
| `GET` | `/db/<db_id>/tables` | Liefert alle sichtbaren Tabellen und Views einer Datenbank. | `company_admin` | Path: `db_id:int` | Liste von Tabellen und Views, Systemtabellen ausgeschlossen |
| `POST` | `/db/<db_id>/key_models` | Liefert verbundene Tabellen-Gruppen auf Basis von Foreign Keys und optional heuristischen Beziehungen. | `company_admin` | Path: `db_id:int`, Body: `start_tables:list[str] | null`, `max_distance:int | null`, `include_all:bool | null` | JSON mit gruppierten Tabellenstrukturen |
| `POST` | `/db/` | Legt einen neuen Datenbank-Eintrag in `db_schema` an. | `company_admin`, `admin` | Body: `user_group:int`, `owner:str`, `url:str | null`, `ip:str | null`, `db_name:str`, `db_description:str | null`, `db_con_id:int` | JSON des neu angelegten DB-Eintrags |
| `POST` | `/db_connection/` | Legt eine neue technische DB-Verbindung an. | `company_admin`, `admin` | Body: `user_group:int`, `owner:str`, `url:str | null`, `ip:str | null`, `server_description:str | null`, `default_user:str | null`, `admin_user:str | null`, `db_type:str` | JSON der neu angelegten Verbindungsdefinition |
| `GET` | `/db_connection/personal_user/` | Liefert den persönlichen DB-Benutzer für eine DB, falls vorhanden. | `admin`, `company_admin` | Query oder Body: `db_id:int` | JSON des persönlichen DB-Benutzers oder leerer Treffer |
| `POST` | `/db_connection/personal_user/` | Legt einen persönlichen DB-Benutzer für eine DB an. | `admin`, `company_admin` | Body: `db_id:int`, `arkana_user_id:str`, `db_user_name:str` | JSON der neu angelegten Benutzerzuordnung |
| `POST` | `/db_connection/user/<user_name>/password` | Setzt oder aktualisiert das Passwort eines technischen DB-Benutzers im Keyring. | `admin`, eigener User, `company_admin` innerhalb der DB-Gruppe | Path: `user_name:str`, Body: `db_id:int`, `password:str` | Status der Passwort-Aktualisierung |
| `POST` | `/frames/execute` | Führt ein `Modelframe` aus und liefert das erzeugte JSON. | Authentifizierter Benutzer | Body: `frame:object`, `input_parameters:object`, `referenced_frames:object` | JSON-Ergebnis des Frame-Executors |

## Rechte-Regeln

| Bereich | Regel |
|---|---|
| Allgemeine DB-Infos | Zugriff für `company_admin` |
| Tabellenlisten | Zugriff für `company_admin`, Systemtabellen sind ausgeschlossen |
| Neue DB anlegen | `company_admin` nur für eigene zugewiesene Gruppen, `admin` für alle Gruppen |
| Persönlichen DB-User anlegen | Nur `admin` oder `company_admin` |
| Passwort setzen | `admin` darf frei setzen, andere Benutzer nur für den eigenen User, `company_admin` nur innerhalb der Gruppe der DB |

## Request-Details

| Endpoint | Parameter | Beschreibung |
|---|---|---|
| `GET /db/<db_id>/` | `db_id` | Eindeutige Datenbank-ID aus `db_schema.db_id` |
| `GET /db/<db_id>/tables` | `db_id` | Ziel-Datenbank für Tabellen- und View-Metadaten |
| `POST /db/<db_id>/key_models` | `start_tables` | Optionaler DFS-Startpunkt als Liste von Tabellen |
| `POST /db/<db_id>/key_models` | `max_distance` | Optional maximale Graph-Tiefe |
| `POST /db/<db_id>/key_models` | `include_all` | Wenn `true`, zusätzlich heuristische Beziehungen ohne Constraint berücksichtigen |
| `POST /db/` | `user_group` | Zielgruppe der DB, muss identisch oder Subgroup der Connection-Gruppe sein |
| `POST /db/` | `owner` | `arkana_user_id` des fachlichen Eigentümers |
| `POST /db/` | `db_con_id` | Referenz auf die bestehende technische Verbindung |
| `POST /db_connection/` | `url` / `ip` | Mindestens eines der beiden Felder muss gesetzt sein |
| `POST /db_connection/` | `db_type` | Erlaubte Werte: `MySQL`, `Supabase`, `PostgreSQL` |
| `POST /db_connection/personal_user/` | `arkana_user_id` | Benutzer-ID aus `arkana_user.user_id` |
| `POST /db_connection/user/<user_name>/password` | `password` | Neues Passwort, Speicherung nur im OS-Keyring |
| `POST /frames/execute` | `frame` | Vollständige `Modelframe`-Definition |
| `POST /frames/execute` | `input_parameters` | Eingabewerte für die Frame-Ausführung |
| `POST /frames/execute` | `referenced_frames` | Optionales Mapping für `model_ref.frame_id` auf weitere Frames |

## Response-Details

| Endpoint | Inhalt |
|---|---|
| `GET /db/<db_id>/` | DB-Metadaten ohne Passwortfelder und ohne persönlichen DB-Benutzer |
| `GET /db/<db_id>/tables` | Liste von Tabellen und Views, ohne Tabellen aus dem Schema `sys` |
| `POST /db/<db_id>/key_models` | Tabellen-Gruppen mit Beziehungen über Foreign Keys und optional Heuristiken |
| `POST /db/` | Neu erzeugter `db_schema`-Eintrag |
| `POST /db_connection/` | Neu erzeugter `db_connection`-Eintrag |
| `GET /db_connection/personal_user/` | Persönliche User-Zuordnung oder kein Treffer |
| `POST /db_connection/personal_user/` | Neu erzeugter `ark_db_personal_user`-Eintrag |
| `POST /db_connection/user/<user_name>/password` | Erfolgs- oder Fehlstatus der Keyring-Aktualisierung |
| `POST /frames/execute` | Ergebnisobjekt mit `frame_id` und generiertem `result` |

## Zusätzliche Regeln

| Thema | Regel |
|---|---|
| Passwortspeicherung | Passwörter werden nicht in SQL gespeichert, sondern nur im OS-Keyring |
| Keyring-Service | Service-Name: `arkana/db_credentials` |
| Keyring-Username | Format: `db:{db_id}\|arkana:{arkana_user_id}\|dbuser:{db_user_name}` |
| Personal User | Pro Benutzer darf pro DB nur ein `ark_db_personal_user` existieren |
| Logging | Laufzeit-Logging in der Anwendung, keine separate Audit-Tabelle |
| Systemtabellen | Alle Tabellen im Schema `sys` sind ausgeschlossen; zusätzlich kann Python `EXCLUDED_SYSTEM_TABLES` verwenden |
| API Basic Auth | Passwörter liegen im separaten Keyring-Service `arkana/api_basic_auth` |

## CLI-Bezug

| Werkzeug | Zweck | Eingaben |
|---|---|---|
| `scripts/cli_set_pw.py` | Setzt das Passwort eines vorhandenen persönlichen DB-Benutzers im Keyring | `db_id oder db_name`, `arkana_username`, `db_username`, neues Passwort |
