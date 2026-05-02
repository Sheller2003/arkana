USE arkana;

CREATE TABLE IF NOT EXISTS arkana_type (
  type_key VARCHAR(64) NOT NULL,
  type_group VARCHAR(32) NOT NULL DEFAULT 'arkana_object',
  type_description VARCHAR(200) NULL,
  PRIMARY KEY (type_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET @has_arkana_type_group := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'arkana_type'
    AND COLUMN_NAME = 'type_group'
);
SET @sql_add_arkana_type_group := IF(
  @has_arkana_type_group = 0,
  'ALTER TABLE arkana_type ADD COLUMN type_group VARCHAR(32) NOT NULL DEFAULT ''arkana_object'' AFTER type_key',
  'SELECT 1'
);
PREPARE stmt FROM @sql_add_arkana_type_group;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

INSERT IGNORE INTO arkana_type (type_key, type_group, type_description) VALUES
  ('ark_notes', 'arkana_object', 'Notes/Notion-like page object');

UPDATE arkana_type
SET type_group = 'arkana_object'
WHERE type_key = 'ark_notes' AND (type_group IS NULL OR type_group = '');

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
