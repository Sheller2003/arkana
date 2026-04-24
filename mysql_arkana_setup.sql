CREATE DATABASE IF NOT EXISTS arkana
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE arkana;

SET SESSION sql_mode = CONCAT_WS(',', @@SESSION.sql_mode, 'NO_AUTO_VALUE_ON_ZERO');

CREATE TABLE IF NOT EXISTS arkana_user (
  user_id VARCHAR(120) NOT NULL,
  user_name VARCHAR(120) NOT NULL,
  user_role ENUM('root', 'admin', 'editor', 'viewer') NOT NULL DEFAULT 'viewer',
  user_storage_db_id BIGINT NULL,
  supabase_user_id VARCHAR(120) NULL,
  supabase_email VARCHAR(255) NULL,
  auth_provider ENUM('local', 'supabase') NOT NULL DEFAULT 'local',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id),
  UNIQUE KEY uq_arkana_user_name (user_name),
  UNIQUE KEY uq_arkana_user_supabase_user_id (supabase_user_id),
  UNIQUE KEY uq_arkana_user_supabase_email (supabase_email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO arkana_user (
  user_id,
  user_name,
  user_role
) VALUES
  ('system', 'system', 'root');

CREATE TABLE IF NOT EXISTS db_connection (
  db_con_id BIGINT NOT NULL AUTO_INCREMENT,
  user_group BIGINT NOT NULL DEFAULT 0,
  owner VARCHAR(120) NOT NULL,
  url VARCHAR(255) NULL,
  ip VARCHAR(255) NULL,
  server_description TEXT NULL,
  default_user VARCHAR(120) NULL,
  admin_user VARCHAR(120) NULL,
  db_type ENUM('MySQL', 'Supabase', 'PostgreSQL') NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (db_con_id),
  KEY idx_db_connection_user_group (user_group),
  KEY idx_db_connection_owner (owner),
  CONSTRAINT fk_db_connection_owner
    FOREIGN KEY (owner) REFERENCES arkana_user(user_id)
    ON DELETE RESTRICT
    ON UPDATE CASCADE,
  CONSTRAINT chk_db_connection_url_or_ip
    CHECK (
      (url IS NOT NULL AND CHAR_LENGTH(TRIM(url)) > 0)
      OR (ip IS NOT NULL AND CHAR_LENGTH(TRIM(ip)) > 0)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS db_schema (
  db_id BIGINT NOT NULL AUTO_INCREMENT,
  db_con_id BIGINT NOT NULL,
  user_group BIGINT NOT NULL DEFAULT 0,
  owner VARCHAR(120) NOT NULL,
  url VARCHAR(255) NULL,
  ip VARCHAR(255) NULL,
  db_name VARCHAR(150) NOT NULL,
  db_description TEXT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (db_id),
  UNIQUE KEY uq_db_schema_connection_name (db_con_id, db_name),
  KEY idx_db_schema_user_group (user_group),
  KEY idx_db_schema_owner (owner),
  CONSTRAINT fk_db_schema_connection
    FOREIGN KEY (db_con_id) REFERENCES db_connection(db_con_id)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT fk_db_schema_owner
    FOREIGN KEY (owner) REFERENCES arkana_user(user_id)
    ON DELETE RESTRICT
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS ark_db_personal_user (
  db_personal_user_id BIGINT NOT NULL AUTO_INCREMENT,
  db_id BIGINT NOT NULL,
  arkana_user_id VARCHAR(120) NOT NULL,
  db_user_name VARCHAR(120) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (db_personal_user_id),
  UNIQUE KEY uq_db_personal_user (db_id, arkana_user_id),
  KEY idx_db_personal_user_name (db_user_name),
  CONSTRAINT fk_db_personal_user_db
    FOREIGN KEY (db_id) REFERENCES db_schema(db_id)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT fk_db_personal_user_user
    FOREIGN KEY (arkana_user_id) REFERENCES arkana_user(user_id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Types available for Arkana objects
CREATE TABLE IF NOT EXISTS arkana_type (
  type_key VARCHAR(16) NOT NULL,
  type_description VARCHAR(200) NULL,
  PRIMARY KEY (type_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Seed basic types
INSERT IGNORE INTO arkana_type (type_key, type_description) VALUES
  ('board', 'Dashboard/Board object'),
  ('ark_notes', 'Notes/Notion-like page object');

-- Ensure a connection and schema with id 0 exist for the main Arkana DB
-- Note: We rely on NO_AUTO_VALUE_ON_ZERO set above to allow explicit 0 inserts.
INSERT IGNORE INTO db_connection (
  db_con_id, user_group, owner, url, ip, server_description, default_user, admin_user, db_type
) VALUES (
  0, 0, 'system', 'mysql://127.0.0.1:3306', NULL, 'Main Arkana DB connection (default)', NULL, NULL, 'MySQL'
);

INSERT IGNORE INTO db_schema (
  db_id, db_con_id, user_group, owner, url, ip, db_name, db_description
) VALUES (
  0, 0, 0, 'system', NULL, NULL, 'arkana', 'Main Arkana schema (default)'
);

CREATE TABLE IF NOT EXISTS arkana_object (
  arkana_id BIGINT NOT NULL AUTO_INCREMENT,
  arkana_type VARCHAR(16) NOT NULL,
  auth_group BIGINT NULL,
  object_key VARCHAR(100) NULL,
  description VARCHAR(100) NULL,
  modeling_db BIGINT NOT NULL DEFAULT 0,
  PRIMARY KEY (arkana_id),
  KEY idx_arkana_object_type (arkana_type),
  KEY idx_arkana_object_auth_group (auth_group),
  KEY idx_arkana_object_modeling_db (modeling_db),
  CONSTRAINT fk_arkana_object_type
    FOREIGN KEY (arkana_type) REFERENCES arkana_type(type_key)
    ON DELETE RESTRICT
    ON UPDATE CASCADE,
  CONSTRAINT fk_arkana_object_modeling_db
    FOREIGN KEY (modeling_db) REFERENCES db_schema(db_id)
    ON DELETE RESTRICT
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS arkana_dashboard_header (
  arkana_id BIGINT NOT NULL,
  arkana_group BIGINT NULL,
  PRIMARY KEY (arkana_id),
  KEY idx_arkana_dashboard_header_group (arkana_group),
  CONSTRAINT fk_arkana_dashboard_header_object
    FOREIGN KEY (arkana_id) REFERENCES arkana_object(arkana_id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Dashboard content table storing Notion-like page data as JSON
CREATE TABLE IF NOT EXISTS arkana_dashboard (
  arkana_id BIGINT NOT NULL,
  content_json JSON NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (arkana_id),
  CONSTRAINT fk_arkana_dashboard_object
  FOREIGN KEY (arkana_id) REFERENCES arkana_object(arkana_id)
  ON DELETE CASCADE
  ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS arkana_notes_header (
  arkana_id BIGINT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (arkana_id),
  CONSTRAINT fk_arkana_notes_header_object
    FOREIGN KEY (arkana_id) REFERENCES arkana_object(arkana_id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS arkana_notes_chapter (
  arkana_object_id BIGINT NOT NULL,
  chapter_id BIGINT NOT NULL,
  order_id INT NOT NULL,
  chapter_key VARCHAR(150) NOT NULL,
  taggs VARCHAR(500) NULL,
  content LONGTEXT NULL,
  files JSON NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (arkana_object_id, chapter_id),
  KEY idx_arkana_notes_chapter_order (arkana_object_id, order_id),
  KEY idx_arkana_notes_chapter_key (arkana_object_id, chapter_key),
  CONSTRAINT fk_arkana_notes_chapter_object
    FOREIGN KEY (arkana_object_id) REFERENCES arkana_object(arkana_id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tracks per-user runtime usage accounting per day
CREATE TABLE IF NOT EXISTS user_runtime_usage_accounting (
  user_id VARCHAR(120) NOT NULL,
  `date` DATE NOT NULL,
  service CHAR(3) NOT NULL DEFAULT 'ark',
  used_time BIGINT NOT NULL DEFAULT 0,          -- seconds
  used_tokens INT NOT NULL DEFAULT 0,
  pay_model INT NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, `date`, service, pay_model),
  KEY idx_urua_date (`date`),
  KEY idx_urua_user (user_id),
  CONSTRAINT fk_urua_user
    FOREIGN KEY (user_id) REFERENCES arkana_user(user_id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET @has_fk_user_storage_db := (
  SELECT COUNT(*)
    FROM information_schema.TABLE_CONSTRAINTS
   WHERE CONSTRAINT_SCHEMA = DATABASE()
     AND TABLE_NAME = 'arkana_user'
     AND CONSTRAINT_NAME = 'fk_arkana_user_storage_db'
     AND CONSTRAINT_TYPE = 'FOREIGN KEY'
);

SET @sql_add_fk_user_storage_db := IF(
  @has_fk_user_storage_db = 0,
  'ALTER TABLE arkana_user ADD CONSTRAINT fk_arkana_user_storage_db FOREIGN KEY (user_storage_db_id) REFERENCES db_schema(db_id) ON DELETE SET NULL ON UPDATE CASCADE',
  'SELECT 1'
);

PREPARE stmt_add_fk_user_storage_db FROM @sql_add_fk_user_storage_db;
EXECUTE stmt_add_fk_user_storage_db;
DEALLOCATE PREPARE stmt_add_fk_user_storage_db;

-- =========================
-- Conditional migration for existing databases created with older scripts
-- Adds missing modeling_db column, index, and FK if not present
-- Ensures required seed rows with id 0 exist for FK default
-- =========================

-- Ensure seed rows exist (id 0) again in case script executed against existing DB
INSERT IGNORE INTO db_connection (
  db_con_id, user_group, owner, url, ip, server_description, default_user, admin_user, db_type
) VALUES (
  0, 0, 'system', 'mysql://127.0.0.1:3306', NULL, 'Main Arkana DB connection (default)', NULL, NULL, 'MySQL'
);

INSERT IGNORE INTO db_schema (
  db_id, db_con_id, user_group, owner, url, ip, db_name, db_description
) VALUES (
  0, 0, 0, 'system', NULL, NULL, 'arkana', 'Main Arkana schema (default)'
);

-- Add modeling_db column if missing
SET @has_modeling_col := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
   WHERE TABLE_SCHEMA = DATABASE()
     AND TABLE_NAME = 'arkana_object'
     AND COLUMN_NAME = 'modeling_db'
);

SET @sql_add_modeling_col := IF(
  @has_modeling_col = 0,
  'ALTER TABLE arkana_object ADD COLUMN modeling_db BIGINT NOT NULL DEFAULT 0 AFTER description',
  'SELECT 1'
);
PREPARE stmt_add_modeling_col FROM @sql_add_modeling_col; EXECUTE stmt_add_modeling_col; DEALLOCATE PREPARE stmt_add_modeling_col;

-- Add index on modeling_db if missing
SET @has_modeling_idx := (
  SELECT COUNT(*) FROM information_schema.STATISTICS
   WHERE TABLE_SCHEMA = DATABASE()
     AND TABLE_NAME = 'arkana_object'
     AND INDEX_NAME = 'idx_arkana_object_modeling_db'
);

SET @sql_add_modeling_idx := IF(
  @has_modeling_idx = 0,
  'ALTER TABLE arkana_object ADD KEY idx_arkana_object_modeling_db (modeling_db)',
  'SELECT 1'
);
PREPARE stmt_add_modeling_idx FROM @sql_add_modeling_idx; EXECUTE stmt_add_modeling_idx; DEALLOCATE PREPARE stmt_add_modeling_idx;

-- Add FK for modeling_db if missing
SET @has_modeling_fk := (
  SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
   WHERE CONSTRAINT_SCHEMA = DATABASE()
     AND TABLE_NAME = 'arkana_object'
     AND CONSTRAINT_NAME = 'fk_arkana_object_modeling_db'
     AND CONSTRAINT_TYPE = 'FOREIGN KEY'
);

SET @sql_add_modeling_fk := IF(
  @has_modeling_fk = 0,
  'ALTER TABLE arkana_object ADD CONSTRAINT fk_arkana_object_modeling_db FOREIGN KEY (modeling_db) REFERENCES db_schema(db_id) ON DELETE RESTRICT ON UPDATE CASCADE',
  'SELECT 1'
);
PREPARE stmt_add_modeling_fk FROM @sql_add_modeling_fk; EXECUTE stmt_add_modeling_fk; DEALLOCATE PREPARE stmt_add_modeling_fk;

-- =========================
-- Conditional migration for existing DBs: create arkana_dashboard table or add missing FK
-- =========================

-- Create arkana_dashboard table if missing (idempotent)
SET @has_dashboard_table := (
  SELECT COUNT(*) FROM information_schema.TABLES
   WHERE TABLE_SCHEMA = DATABASE()
     AND TABLE_NAME = 'arkana_dashboard'
);

SET @sql_create_dashboard := IF(
  @has_dashboard_table = 0,
  'CREATE TABLE arkana_dashboard (\n    arkana_id BIGINT NOT NULL,\n    content_json JSON NULL,\n    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,\n    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,\n    PRIMARY KEY (arkana_id),\n    CONSTRAINT fk_arkana_dashboard_object FOREIGN KEY (arkana_id) REFERENCES arkana_object(arkana_id) ON DELETE CASCADE ON UPDATE CASCADE\n  ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci',
  'SELECT 1'
);
PREPARE stmt_create_dashboard FROM @sql_create_dashboard; EXECUTE stmt_create_dashboard; DEALLOCATE PREPARE stmt_create_dashboard;

-- Ensure FK exists if table already existed without it
SET @has_dashboard_fk := (
  SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
   WHERE CONSTRAINT_SCHEMA = DATABASE()
     AND TABLE_NAME = 'arkana_dashboard'
     AND CONSTRAINT_NAME = 'fk_arkana_dashboard_object'
     AND CONSTRAINT_TYPE = 'FOREIGN KEY'
);

SET @sql_add_dashboard_fk := IF(
  @has_dashboard_fk = 0,
  'ALTER TABLE arkana_dashboard ADD CONSTRAINT fk_arkana_dashboard_object FOREIGN KEY (arkana_id) REFERENCES arkana_object(arkana_id) ON DELETE CASCADE ON UPDATE CASCADE',
  'SELECT 1'
);
PREPARE stmt_add_dashboard_fk FROM @sql_add_dashboard_fk; EXECUTE stmt_add_dashboard_fk; DEALLOCATE PREPARE stmt_add_dashboard_fk;

-- =========================
-- Dashboard fields table (for ordered fields/blocks per dashboard)
-- Requirements: historical environments may have table `dashboard_fields`.
-- The application code now uses `arkana_dashboard_fields`.
-- Strategy:
--   1) Ensure legacy `dashboard_fields` exists and has column `taggs` (idempotent).
--   2) Ensure `arkana_dashboard_fields` exists:
--      - If legacy `dashboard_fields` exists and new one does not, create an updatable VIEW
--        `arkana_dashboard_fields` on top of `dashboard_fields` for compatibility.
--      - If neither exists, create a real TABLE `arkana_dashboard_fields` with the desired schema.
-- =========================

-- Create dashboard_fields if missing
SET @has_dash_fields := (
  SELECT COUNT(*) FROM information_schema.TABLES
   WHERE TABLE_SCHEMA = DATABASE()
     AND TABLE_NAME = 'dashboard_fields'
);

SET @sql_create_dash_fields := IF(
  @has_dash_fields = 0,
  'CREATE TABLE dashboard_fields (
      field_id BIGINT NOT NULL AUTO_INCREMENT,
      arkana_id BIGINT NOT NULL,
      order_id INT NOT NULL,
      field_key VARCHAR(100) NULL,
      field_type VARCHAR(40) NULL,
      config_json JSON NULL,
      taggs VARCHAR(500) NULL,
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      PRIMARY KEY (field_id),
      KEY idx_dashboard_fields_arkana (arkana_id),
      KEY idx_dashboard_fields_order (arkana_id, order_id),
      CONSTRAINT fk_dashboard_fields_object FOREIGN KEY (arkana_id)
        REFERENCES arkana_object(arkana_id) ON DELETE CASCADE ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci',
  'SELECT 1'
);
PREPARE stmt_create_dash_fields FROM @sql_create_dash_fields; EXECUTE stmt_create_dash_fields; DEALLOCATE PREPARE stmt_create_dash_fields;

-- Ensure column `taggs` exists on dashboard_fields
SET @has_dash_fields_taggs := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
   WHERE TABLE_SCHEMA = DATABASE()
     AND TABLE_NAME = 'dashboard_fields'
     AND COLUMN_NAME = 'taggs'
);

SET @sql_add_dash_fields_taggs := IF(
  @has_dash_fields_taggs = 0,
  'ALTER TABLE dashboard_fields ADD COLUMN taggs VARCHAR(500) NULL AFTER config_json',
  'SELECT 1'
);
PREPARE stmt_add_dash_fields_taggs FROM @sql_add_dash_fields_taggs; EXECUTE stmt_add_dash_fields_taggs; DEALLOCATE PREPARE stmt_add_dash_fields_taggs;

-- =========================
-- Create or map arkana_dashboard_fields used by the application
-- =========================

-- Check for presence of the preferred name
SET @has_arkana_dash_fields := (
  SELECT COUNT(*) FROM information_schema.TABLES
   WHERE TABLE_SCHEMA = DATABASE()
     AND TABLE_NAME = 'arkana_dashboard_fields'
);

-- If the preferred table/view does not exist but legacy table exists, create a VIEW for compatibility
SET @sql_create_arkana_dash_fields_view := IF(
  @has_arkana_dash_fields = 0 AND @has_dash_fields = 1,
  'CREATE OR REPLACE VIEW arkana_dashboard_fields AS \n\
   SELECT field_id, arkana_id, order_id, field_key, field_type, config_json, taggs, created_at, updated_at\n\
     FROM dashboard_fields',
  'SELECT 1'
);
PREPARE stmt_create_arkana_dash_fields_view FROM @sql_create_arkana_dash_fields_view; EXECUTE stmt_create_arkana_dash_fields_view; DEALLOCATE PREPARE stmt_create_arkana_dash_fields_view;

-- Recompute flag (view creation registers in TABLES)
SET @has_arkana_dash_fields := (
  SELECT COUNT(*) FROM information_schema.TABLES
   WHERE TABLE_SCHEMA = DATABASE()
     AND TABLE_NAME = 'arkana_dashboard_fields'
);

-- If neither legacy nor preferred exists, create the preferred TABLE now
SET @sql_create_arkana_dash_fields_table := IF(
  @has_arkana_dash_fields = 0 AND @has_dash_fields = 0,
  'CREATE TABLE arkana_dashboard_fields (\n\
      field_id BIGINT NOT NULL AUTO_INCREMENT,\n\
      arkana_id BIGINT NOT NULL,\n\
      order_id INT NOT NULL,\n\
      field_key VARCHAR(100) NULL,\n\
      field_type VARCHAR(40) NULL,\n\
      config_json JSON NULL,\n\
      taggs VARCHAR(500) NULL,\n\
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,\n\
      updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,\n\
      PRIMARY KEY (field_id),\n\
      KEY idx_arkana_dashboard_fields_arkana (arkana_id),\n\
      KEY idx_arkana_dashboard_fields_order (arkana_id, order_id),\n\
      CONSTRAINT fk_arkana_dashboard_fields_object FOREIGN KEY (arkana_id)\n\
        REFERENCES arkana_object(arkana_id) ON DELETE CASCADE ON UPDATE CASCADE\n\
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci',
  'SELECT 1'
);
PREPARE stmt_create_arkana_dash_fields_table FROM @sql_create_arkana_dash_fields_table; EXECUTE stmt_create_arkana_dash_fields_table; DEALLOCATE PREPARE stmt_create_arkana_dash_fields_table;

-- If the preferred name is a real TABLE, ensure indexes exist (views cannot have indexes)
SET @is_arkana_dash_fields_base_table := (
  SELECT CASE WHEN TABLE_TYPE = 'BASE TABLE' THEN 1 ELSE 0 END
    FROM information_schema.TABLES
   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'arkana_dashboard_fields'
);

-- Add missing index on (arkana_id) for preferred table
SET @has_idx_arkana_fields_arkana := (
  SELECT COUNT(*) FROM information_schema.STATISTICS
   WHERE TABLE_SCHEMA = DATABASE()
     AND TABLE_NAME = 'arkana_dashboard_fields'
     AND INDEX_NAME = 'idx_arkana_dashboard_fields_arkana'
);
SET @sql_add_idx_arkana_fields_arkana := IF(
  @is_arkana_dash_fields_base_table = 1 AND @has_idx_arkana_fields_arkana = 0,
  'ALTER TABLE arkana_dashboard_fields ADD KEY idx_arkana_dashboard_fields_arkana (arkana_id)',
  'SELECT 1'
);
PREPARE stmt_add_idx_arkana_fields_arkana FROM @sql_add_idx_arkana_fields_arkana; EXECUTE stmt_add_idx_arkana_fields_arkana; DEALLOCATE PREPARE stmt_add_idx_arkana_fields_arkana;

-- Add missing composite index on (arkana_id, order_id) for preferred table
SET @has_idx_arkana_fields_order := (
  SELECT COUNT(*) FROM information_schema.STATISTICS
   WHERE TABLE_SCHEMA = DATABASE()
     AND TABLE_NAME = 'arkana_dashboard_fields'
     AND INDEX_NAME = 'idx_arkana_dashboard_fields_order'
);
SET @sql_add_idx_arkana_fields_order := IF(
  @is_arkana_dash_fields_base_table = 1 AND @has_idx_arkana_fields_order = 0,
  'ALTER TABLE arkana_dashboard_fields ADD KEY idx_arkana_dashboard_fields_order (arkana_id, order_id)',
  'SELECT 1'
);
PREPARE stmt_add_idx_arkana_fields_order FROM @sql_add_idx_arkana_fields_order; EXECUTE stmt_add_idx_arkana_fields_order; DEALLOCATE PREPARE stmt_add_idx_arkana_fields_order;

SET @has_idx_object_key := (
  SELECT COUNT(*) FROM information_schema.STATISTICS
   WHERE TABLE_SCHEMA = DATABASE()
     AND TABLE_NAME = 'arkana_object'
     AND INDEX_NAME = 'idx_arkana_object_object_key'
);
SET @sql_add_idx_object_key := IF(
  @has_idx_object_key = 0,
  'ALTER TABLE arkana_object ADD KEY idx_arkana_object_object_key (object_key)',
  'SELECT 1'
);
PREPARE stmt_add_idx_object_key FROM @sql_add_idx_object_key; EXECUTE stmt_add_idx_object_key; DEALLOCATE PREPARE stmt_add_idx_object_key;

-- =========================
-- RENAME/MIGRATE: dashboard fields -> dashboard cells
-- Target table/columns:
--   Table: arkana_dashboard_cells
--   Columns: cell_id (PK per dashboard, NOT AUTO_INCREMENT), arkana_object_id, order_id, cell_key, cell_type, taggs, created_at, updated_at
--   FK: arkana_object_id -> arkana_object(arkana_id)
-- Migration strategy:
--   - If arkana_dashboard_cells already exists: nothing to do.
--   - Else if arkana_dashboard_fields exists as BASE TABLE: RENAME TABLE -> arkana_dashboard_cells, then RENAME columns field_* -> cell_* and arkana_id -> arkana_object_id when present.
--   - Else if arkana_dashboard_fields exists as VIEW: CREATE TABLE arkana_dashboard_cells and copy data from the view (mapping columns), DROP the view.
--   - Else: CREATE TABLE arkana_dashboard_cells fresh.

-- Detect existing tables
SET @has_cells_table := (
  SELECT COUNT(*) FROM information_schema.TABLES
   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'arkana_dashboard_cells'
);

SET @has_fields_table := (
  SELECT COUNT(*) FROM information_schema.TABLES
   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'arkana_dashboard_fields'
);

SET @fields_is_base_table := (
  SELECT CASE WHEN TABLE_TYPE = 'BASE TABLE' THEN 1 ELSE 0 END
    FROM information_schema.TABLES
   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'arkana_dashboard_fields'
);

-- Case 1: Create fresh table if neither exists
SET @sql_create_cells_if_missing := IF(
  @has_cells_table = 0 AND @has_fields_table = 0,
  'CREATE TABLE arkana_dashboard_cells (\n\
      cell_id BIGINT NOT NULL,\n\
      arkana_object_id BIGINT NOT NULL,\n\
      order_id INT NOT NULL,\n\
      prev_id BIGINT NOT NULL DEFAULT 0,\n\
      cell_key VARCHAR(100) NULL,\n\
      cell_type VARCHAR(40) NULL,\n\
      taggs VARCHAR(500) NULL,\n\
      content JSON NULL,\n\
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,\n\
      updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,\n\
      KEY idx_arkana_dashboard_cells_arkana (arkana_object_id),\n\
      KEY idx_arkana_dashboard_cells_order (arkana_object_id, order_id),\n\
      KEY idx_arkana_dashboard_cells_prev (arkana_object_id, prev_id),\n\
      CONSTRAINT fk_arkana_dashboard_cells_object FOREIGN KEY (arkana_object_id)\n\
        REFERENCES arkana_object(arkana_id) ON DELETE CASCADE ON UPDATE CASCADE\n\
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci',
  'SELECT 1'
);
PREPARE stmt_create_cells_if_missing FROM @sql_create_cells_if_missing; EXECUTE stmt_create_cells_if_missing; DEALLOCATE PREPARE stmt_create_cells_if_missing;

-- Case 2: Rename base table and columns if fields exists as base table and cells missing
SET @sql_rename_table := IF(
  @has_cells_table = 0 AND @has_fields_table = 1 AND @fields_is_base_table = 1,
  'RENAME TABLE arkana_dashboard_fields TO arkana_dashboard_cells',
  'SELECT 1'
);
PREPARE stmt_rename_table FROM @sql_rename_table; EXECUTE stmt_rename_table; DEALLOCATE PREPARE stmt_rename_table;

-- After possible rename, recompute presence
SET @has_cells_table := (
  SELECT COUNT(*) FROM information_schema.TABLES
   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'arkana_dashboard_cells'
);

-- Conditionally rename columns on arkana_dashboard_cells
SET @has_col_field_id := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'arkana_dashboard_cells' AND COLUMN_NAME = 'field_id'
);
SET @has_col_cell_id := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'arkana_dashboard_cells' AND COLUMN_NAME = 'cell_id'
);
SET @sql_rename_field_id := IF(
  @has_cells_table = 1 AND @has_col_field_id = 1 AND @has_col_cell_id = 0,
  'ALTER TABLE arkana_dashboard_cells CHANGE COLUMN field_id cell_id BIGINT NOT NULL',
  'SELECT 1'
);
PREPARE stmt_rename_field_id FROM @sql_rename_field_id; EXECUTE stmt_rename_field_id; DEALLOCATE PREPARE stmt_rename_field_id;

SET @has_col_field_key := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'arkana_dashboard_cells' AND COLUMN_NAME = 'field_key'
);
SET @has_col_cell_key := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'arkana_dashboard_cells' AND COLUMN_NAME = 'cell_key'
);
SET @sql_rename_field_key := IF(
  @has_cells_table = 1 AND @has_col_field_key = 1 AND @has_col_cell_key = 0,
  'ALTER TABLE arkana_dashboard_cells CHANGE COLUMN field_key cell_key VARCHAR(100) NULL',
  'SELECT 1'
);
PREPARE stmt_rename_field_key FROM @sql_rename_field_key; EXECUTE stmt_rename_field_key; DEALLOCATE PREPARE stmt_rename_field_key;

SET @has_col_field_type := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'arkana_dashboard_cells' AND COLUMN_NAME = 'field_type'
);
SET @has_col_cell_type := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'arkana_dashboard_cells' AND COLUMN_NAME = 'cell_type'
);
SET @sql_rename_field_type := IF(
  @has_cells_table = 1 AND @has_col_field_type = 1 AND @has_col_cell_type = 0,
  'ALTER TABLE arkana_dashboard_cells CHANGE COLUMN field_type cell_type VARCHAR(40) NULL',
  'SELECT 1'
);
PREPARE stmt_rename_field_type FROM @sql_rename_field_type; EXECUTE stmt_rename_field_type; DEALLOCATE PREPARE stmt_rename_field_type;

SET @has_col_arkana_id := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'arkana_dashboard_cells' AND COLUMN_NAME = 'arkana_id'
);
SET @has_col_arkana_object_id := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'arkana_dashboard_cells' AND COLUMN_NAME = 'arkana_object_id'
);
SET @sql_rename_arkana_id := IF(
  @has_cells_table = 1 AND @has_col_arkana_id = 1 AND @has_col_arkana_object_id = 0,
  'ALTER TABLE arkana_dashboard_cells CHANGE COLUMN arkana_id arkana_object_id BIGINT NOT NULL',
  'SELECT 1'
);
PREPARE stmt_rename_arkana_id FROM @sql_rename_arkana_id; EXECUTE stmt_rename_arkana_id; DEALLOCATE PREPARE stmt_rename_arkana_id;

-- Case 3: If fields exists as VIEW and cells missing, create table and copy data, then drop view
SET @needs_copy_from_view := (
  SELECT CASE WHEN @has_cells_table = 0 AND @has_fields_table = 1 AND @fields_is_base_table = 0 THEN 1 ELSE 0 END
);

SET @sql_create_cells_from_view := IF(
  @needs_copy_from_view = 1,
  'CREATE TABLE arkana_dashboard_cells (\n\
      cell_id BIGINT NOT NULL,\n\
      arkana_object_id BIGINT NOT NULL,\n\
      order_id INT NOT NULL,\n\
      prev_id BIGINT NOT NULL DEFAULT 0,\n\
      cell_key VARCHAR(100) NULL,\n\
      cell_type VARCHAR(40) NULL,\n\
      taggs VARCHAR(500) NULL,\n\
      content JSON NULL,\n\
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,\n\
      updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,\n\
      KEY idx_arkana_dashboard_cells_arkana (arkana_object_id),\n\
      KEY idx_arkana_dashboard_cells_order (arkana_object_id, order_id),\n\
      KEY idx_arkana_dashboard_cells_prev (arkana_object_id, prev_id),\n\
      CONSTRAINT fk_arkana_dashboard_cells_object FOREIGN KEY (arkana_object_id) REFERENCES arkana_object(arkana_id) ON DELETE CASCADE ON UPDATE CASCADE\n\
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci',
  'SELECT 1'
);
PREPARE stmt_create_cells_from_view FROM @sql_create_cells_from_view; EXECUTE stmt_create_cells_from_view; DEALLOCATE PREPARE stmt_create_cells_from_view;

SET @sql_copy_from_view := IF(
  @needs_copy_from_view = 1,
  'INSERT INTO arkana_dashboard_cells (cell_id, arkana_object_id, order_id, cell_key, cell_type, taggs, created_at, updated_at)\n\
   SELECT field_id, COALESCE(arkana_object_id, arkana_id), order_id, field_key, field_type, taggs, created_at, updated_at\n\
     FROM arkana_dashboard_fields',
  'SELECT 1'
);
PREPARE stmt_copy_from_view FROM @sql_copy_from_view; EXECUTE stmt_copy_from_view; DEALLOCATE PREPARE stmt_copy_from_view;

SET @sql_drop_view_fields := IF(
  @needs_copy_from_view = 1,
  'DROP VIEW IF EXISTS arkana_dashboard_fields',
  'SELECT 1'
);
PREPARE stmt_drop_view_fields FROM @sql_drop_view_fields; EXECUTE stmt_drop_view_fields; DEALLOCATE PREPARE stmt_drop_view_fields;

-- Optional: provide backward-compatibility view mapping old name to new table
SET @has_fields_table := (
  SELECT COUNT(*) FROM information_schema.TABLES
   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'arkana_dashboard_fields'
);
SET @sql_create_compat_view := IF(
  @has_fields_table = 0,
  'CREATE OR REPLACE VIEW arkana_dashboard_fields AS SELECT\n\
     cell_id AS field_id,\n\
     arkana_object_id AS arkana_id,\n\
     order_id,\n\
     cell_key AS field_key,\n\
     cell_type AS field_type,\n\
     NULL AS config_json,\n\
     taggs,\n\
     created_at,\n\
     updated_at\n\
   FROM arkana_dashboard_cells',
  'SELECT 1'
);
PREPARE stmt_create_compat_view FROM @sql_create_compat_view; EXECUTE stmt_create_compat_view; DEALLOCATE PREPARE stmt_create_compat_view;

-- =========================
-- Conditional alters to add missing columns prev_id and content on existing arkana_dashboard_cells
-- =========================

-- Add prev_id (linked-list ordering) if missing
SET @has_col_prev_id := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'arkana_dashboard_cells' AND COLUMN_NAME = 'prev_id'
);
SET @sql_add_prev_id := IF(
  @has_col_prev_id = 0 AND @has_cells_table = 1,
  'ALTER TABLE arkana_dashboard_cells ADD COLUMN prev_id BIGINT NOT NULL DEFAULT 0 AFTER order_id',
  'SELECT 1'
);
PREPARE stmt_add_prev_id FROM @sql_add_prev_id; EXECUTE stmt_add_prev_id; DEALLOCATE PREPARE stmt_add_prev_id;

-- Add index on (arkana_object_id, prev_id) if missing
SET @has_idx_prev := (
  SELECT COUNT(*) FROM information_schema.STATISTICS
   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'arkana_dashboard_cells' AND INDEX_NAME = 'idx_arkana_dashboard_cells_prev'
);
SET @sql_add_idx_prev := IF(
  @has_idx_prev = 0 AND @has_cells_table = 1,
  'ALTER TABLE arkana_dashboard_cells ADD KEY idx_arkana_dashboard_cells_prev (arkana_object_id, prev_id)',
  'SELECT 1'
);
PREPARE stmt_add_idx_prev FROM @sql_add_idx_prev; EXECUTE stmt_add_idx_prev; DEALLOCATE PREPARE stmt_add_idx_prev;

-- Add content JSON if missing
SET @has_col_content := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'arkana_dashboard_cells' AND COLUMN_NAME = 'content'
);
SET @sql_add_content := IF(
  @has_col_content = 0 AND @has_cells_table = 1,
  'ALTER TABLE arkana_dashboard_cells ADD COLUMN content JSON NULL AFTER taggs',
  'SELECT 1'
);
PREPARE stmt_add_content FROM @sql_add_content; EXECUTE stmt_add_content; DEALLOCATE PREPARE stmt_add_content;
