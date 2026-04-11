Baue einen DB-speicher als SQL-Datenbank.
Ein DB-eintrag soll folgende eigenschaften haben:

db_schema
-db_id:int
-user_group:int default 0 muss identisch oder subgroup of db_connection sein
- owner:str (arkana_user_id)
- url:str
- ip:str
- db_name:str
- db_description:str


db_connection:
-db_con_id:int
-user_group:int default 0
- owner:str (arkana_user_id)
- url:str 
- ip:str url oder ip adresse muss befüllt sein.
- server_description:str 
- default_user:str
- admin_user:str
- db_type: DB_TYPE(MySQL, Supabase, PostgreSQL)

the password of users should be stored in keyring. If a user has for a db its own user: use this user and password.
für das Keyring-Verfahren soll verschlüsselt gespeichert werden.

### db_personal_user:
- db_id:int
- arkana_user_id:str (arkana_user_id)
- db_user_name:str

the key in keyring should be decoded with the db_user_name, the user_id and a given user_password.
pro user darf pro db nur ein personal db user existiren


## user groups:
0: default -> open for all
1: allowed for owners only
2: allowed for owners and admins
10: company specific
.... company groups

user_group:
    - group_id:int
    - group_name:str
    - group_description:str
    - group_owner:str (arkana_user_id)
    - parent_group_id:int

user_group_user:
    - user_id:str (arkana_user_id)
    - group_id:int
    - role:str

user:
is only for db_connection. can't be redefined for single DBs
- user_id:str (arkana_user_id)
- user_name:str
- user_role: user_role(werteliste: `root`, `admin`, `editor`, `viewer`)
- user_storage_db_id:int zeigt auf die db welche den user verwaltet(dummy)


Service urls:
get /db/<db_id>/ -> general db infos as json, no password or personal user; role: company_admin;
get /db/<db_id>/tables -> returns all tables and views (exclude sys-tables);  role: company_admin;
post /db/<db_id>/key_models -> returns grouped (like in graphes connected Nodes) tables (connected via forgein keys);  role: company_admin;
- auch heuristische Beziehungen ohne Constraint if parameter include_all=true.
- if parameter start_tables in json_body: start with dfs from this table (optional parameter: max_distance)
- if no specified group all tables.
post /db/ -> create new db role: company_admin is only allowed to create for own assigned groups, admin is allowed to create for all;
post /db_connection/ create new db connection
get /db_connection/personal_user/ get personal user(if exist); parameter: db_id
post /db_connection/personal_user/ create personal user(if exist); parameter: db_id only allowed for admin or company_admin
post /db_connection/user/<user_name>/password
- set new pw; for all users != admin this is only allowed for own user
- for company_admin its only allowed if they are in the group of the db





db_object
- load_connection(user)
  - if personal user use personal user else use default user
- load_admin_connection()
  - only allowed for admin or company_admin
- check_user_is_allowed(user)
  - if root: show all
  - if admin: show only if group lv != 1
  - for al other users raise exception if they are not assignet to regarding group or the owner of the group
  - if check failes close all connections
- run_command(command:str)
  - first run check_user_is_allowed
  - then run command
- close_connections()
- get_table_object(table)
- get_table()
- get_tables()

---

## Ergänzung: vorgeschlagenes MySQL-Skript

Eine erste Umsetzung liegt in der Datei [mysql_arkana_setup.sql](/Users/sheller2003/PycharmProjects/arkanaMDD/mysql_arkana_setup.sql).

Die Datei erzeugt in der MySQL-Datenbank `arkana` die Tabellen:

- `arkana_user`
- `user_group`
- `user_group_user`
- `db_connection`
- `db_schema`
- `ark_db_personal_user`

Logging-Entscheidung:

- Berechtigungs- und Laufzeitereignisse werden nicht in einer zusätzlichen SQL-Tabelle gespeichert.
- Logging erfolgt als Laufzeit-Logging in der Anwendung.


## Ergänzung: vorgeschlagene Python-Objekte

### ArkanaUser

Parameter:

- `user_id: str`
- `user_name: str`
- `user_role: str`
- `user_storage_db_id: int | None`

Methoden:

- `is_root() -> bool`
  - Prüft, ob der Benutzer globale Root-Rechte besitzt.
- `is_admin() -> bool`
  - Prüft, ob der Benutzer die Rolle `admin` hat.


### UserGroup

Parameter:

- `group_id: int`
- `group_name: str`
- `group_description: str | None`
- `group_owner: str`
- `parent_group_id: int | None`

Methoden:

- `is_public() -> bool`
  - Prüft, ob es sich um die Standardgruppe `0` handelt.
- `has_parent() -> bool`
  - Prüft, ob eine vererbte Eltern-Gruppe existiert.

### UserGroupAssignment

Parameter:

- `user_id: int`
- `group_id: int`
- `role: str`

Methoden:

- `is_owner() -> bool`
  - Prüft, ob die Zuordnung die Gruppenrolle `owner` trägt.
- `is_admin_member() -> bool`
  - Prüft, ob die Zuordnung eine administrative Gruppenrolle besitzt.

### DBConnection

Parameter:

- `db_con_id: int`
- `user_group: int`
- `owner: str`
- `url: str | None`
- `ip: str | None`
- `server_description: str | None`
- `default_user: str | None`
- `admin_user: str | None`
- `db_type: str`

Methoden:

- `build_engine_url() -> str`
  - Baut aus den gespeicherten Verbindungsdaten eine nutzbare Verbindungs-URL.
- `validate_db_type() -> None`
  - Prüft, ob `db_type` zu einem unterstützten Backend gehört.

### DBSchema

Parameter:

- `db_id: int`
- `db_con_id: int`
- `user_group: int`
- `owner: str`
- `url: str | None`
- `ip: str | None`
- `db_name: str`
- `db_description: str | None`

Methoden:

- `qualified_name() -> str`
  - Liefert den lesbaren Namen der Ziel-Datenbank.
- `effective_group_id() -> int`
  - Liefert die effektive Benutzergruppe der Datenbank.

### DBPersonalUser

Parameter:

- `db_id: int`
- `arkana_user_id: int`
- `db_user_name: str`

Methoden:

- `keyring_key(user_id: int, db_user_name: str) -> str`
  - Liefert den technischen Schlüssel für den Zugriff auf den Password-Eintrag im Keyring.
- `matches_user(user_id: int) -> bool`
  - Prüft, ob der Personal-User zum angefragten Arkana-Benutzer gehört.

### DBObject

Parameter:

- `db_schema: DBSchema`
- `connection: DBConnection`
- `current_user: ArkanaUser | None = None`
- `sql_connection: object | None = None`
- `admin_sql_connection: object | None = None`

Methoden:

- `load_connection(user: ArkanaUser) -> object`
  - Lädt eine normale DB-Verbindung für den Benutzer.
  - Verwendet `ark_db_personal_user`, falls vorhanden, sonst `default_user`.
  - falls `ark_db_personal_user` eintrag vorhanden, aber kein pw raise error.
- `load_admin_connection() -> object`
  - Lädt eine administrative Verbindung.
  - Nur für `root` oder `admin` erlaubt.
  - `root` immer implizit immer erlaubt.
- `check_user_is_allowed(user: ArkanaUser) -> None`
  - Prüft die Leseberechtigung auf Basis von Rolle, Gruppenzuordnung und Gruppeneigentümer.
  - Schließt bei Fehlern alle offenen Verbindungen.
- `run_command(command: str) -> object`
  - Führt einen SQL-Befehl nach erfolgreicher Berechtigungsprüfung aus.
  - ist für alle aufrufbar, solange keine user kritischen Befehle durchgeführt werden, diese dürfen nur vom admin oder root.
  - user kritisch = create/delete user add auth etc.
  - `SELECT` und auch DDL/DML erlaubt.
- `close_connections() -> None`
  - Schließt normale und administrative Verbindungen sauber.
- `get_table_object(table: str) -> object`
  - Liefert ein Tabellenobjekt oder einen Metadaten-Wrapper für eine Tabelle.
  - Table_object:
    - table_name:str
    - get_primary_keys()
    - get_forgain_keys()
    - get_fields()
    - get_nr_of_entrys()
    - description
- `get_table(table: str) -> dict`
  - Liefert Metadaten zu genau einer Tabelle.
- `get_tables() -> list[dict]`
  - Liefert alle sichtbaren Tabellen und Views der Ziel-Datenbank.

## Ergänzung: Service-Parameter

### `GET /db/<db_id>/`

Parameter:

- `db_id: int`

Antwort:

- Allgemeine Datenbankinformationen als JSON.
- Keine Passwörter.
- Kein `personal_user`.

### `GET /db/<db_id>/tables`

Parameter:

- `db_id: int`

Antwort:

- Liste aller Tabellen und Views.

### `POST /db/<db_id>/key_models`

Parameter:

- `db_id: int`
- `start_tables: list[str] | None`
- `max_distance: int | None`

Antwort:

- Gruppierte Tabellenstrukturen, die über Foreign Keys verbunden sind.

### `POST /db/`

Parameter:

- `user_group: int`
- `owner: str`
- `url: str | None`
- `ip: str | None`
- `db_name: str`
- `db_description: str | None`
- `db_con_id: int`

Antwort:

- Neu angelegte Datenbank-Metadaten.

### `POST /db_connection/`

Parameter:

- `user_group: int`
- `owner: str`
- `url: str | None`
- `ip: str | None`
- `server_description: str | None`
- `default_user: str | None`
- `admin_user: str | None`
- `db_type: str`

Antwort:

- Neu angelegte Verbindungsdefinition.

### `GET /db_connection/personal_user/`

Parameter:

- `db_id: int`

Antwort:

- Persönlichen DB-Benutzer, falls vorhanden.

### `POST /db_connection/personal_user/`

Parameter:

- `db_id: int`
- `arkana_user_id: int`
- `db_user_name: str`

Antwort:

- Neu angelegte persönliche Benutzerzuordnung.

### `POST /db_connection/user/<user_name>/password`

Parameter:

- `user_name: str`
- `db_id: int`
- `password: str`

Antwort:

- Status der Passwort-Aktualisierung im Keyring.
- zusätzlich wird die Eingabe des aktuellen Passworts verlangt.
- es soll im terminal möglich sein über das skript cli_set_pw das paswort ohne abfrage des alten pws zu setzen
  - frag nach db
  - frag nach arkana_username
  - frag nach db_username
  - if no entry exist raise error and terminate
  - frag nach neuem pw

## Ergänzung: erneute Prüfung / umgesetzt

- `[todo-check]` `arkana_user_id` ist im SQL-Skript jetzt konsequent als `VARCHAR(120)` modelliert.
- `[todo-check]` `owner` und `group_owner` sind im SQL-Skript jetzt per Foreign Key an `arkana_user(user_id)` gebunden.
- `[todo-check]` `db_schema.user_group` wird im SQL-Skript jetzt über Trigger validiert: erlaubt sind nur identische Gruppen oder Subgruppen der `db_connection.user_group`.
- `[todo-check]` `db_connection.url` oder `db_connection.ip` wird im SQL-Skript jetzt per `CHECK`-Constraint erzwungen.
- `[todo-check]` `db_type` ist im SQL-Skript auf `ENUM('MySQL', 'Supabase', 'PostgreSQL')` angepasst.
- `[todo-check]` `user_storage_db_id` referenziert im SQL-Skript jetzt `db_schema(db_id)`.
- `[todo-check]` Systemtabellen für `GET /db/<db_id>/tables` sind alle Tabellen aus dem Schema `sys`; zusätzlich soll in Python eine Konstantenliste `EXCLUDED_SYSTEM_TABLES` für explizit auszuschließende Tabellen verwendet werden.
- `[todo-check]` Für Keyring wird als Standardweg das OS-Keyring verwendet; der Service-Name soll `arkana/db_credentials` sein, der Username im Keyring soll dem Schema `db:{db_id}|arkana:{arkana_user_id}|dbuser:{db_user_name}` folgen. Das Passwort wird nur im Keyring gehalten, die Verschlüsselung übernimmt der jeweilige Keyring-Backend-Provider des Betriebssystems.
- `[todo-check]` Das SQL-Skript aktiviert `NO_AUTO_VALUE_ON_ZERO`, damit `group_id = 0` stabil angelegt werden kann.
- `[todo-check]` `db_permission_audit` wurde aus dem SQL-Skript entfernt; Logging ist als Laufzeit-Logging vorgesehen.
- `TODO`: Die Trigger-Lösung für Gruppenhierarchien setzt MySQL 8.x mit `WITH RECURSIVE` voraus. Falls MySQL 5.7 unterstützt werden muss, braucht es stattdessen eine andere Validierungsstrategie.
- `TODO`: Die Python-Konstante `EXCLUDED_SYSTEM_TABLES` ist fachlich festgelegt, aber noch nicht als Code-Datei im Projekt angelegt.
