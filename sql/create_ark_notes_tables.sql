USE arkana;

CREATE TABLE IF NOT EXISTS arkana_type (
  type_key VARCHAR(16) NOT NULL,
  type_description VARCHAR(200) NULL,
  PRIMARY KEY (type_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO arkana_type (type_key, type_description) VALUES
  ('ark_notes', 'Notes/Notion-like page object');

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
