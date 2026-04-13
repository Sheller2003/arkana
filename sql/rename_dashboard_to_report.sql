USE arkana;

SET FOREIGN_KEY_CHECKS = 0;

RENAME TABLE arkana_dashboard_header TO arkana_report_header;
RENAME TABLE arkana_dashboard TO arkana_report;
RENAME TABLE arkana_dashboard_cells TO arkana_report_cells;

SET FOREIGN_KEY_CHECKS = 1;

ALTER TABLE arkana_report_header
  DROP FOREIGN KEY fk_arkana_dashboard_header_object,
  DROP INDEX idx_arkana_dashboard_header_group;

ALTER TABLE arkana_report_header
  ADD KEY idx_arkana_report_header_group (arkana_group),
  ADD CONSTRAINT fk_arkana_report_header_object
    FOREIGN KEY (arkana_id) REFERENCES arkana_object(arkana_id)
    ON DELETE CASCADE
    ON UPDATE CASCADE;

ALTER TABLE arkana_report
  DROP FOREIGN KEY fk_arkana_dashboard_object;

ALTER TABLE arkana_report
  ADD CONSTRAINT fk_arkana_report_object
    FOREIGN KEY (arkana_id) REFERENCES arkana_object(arkana_id)
    ON DELETE CASCADE
    ON UPDATE CASCADE;

ALTER TABLE arkana_report_cells
  DROP FOREIGN KEY fk_arkana_dashboard_cells_object,
  DROP INDEX idx_arkana_dashboard_cells_arkana,
  DROP INDEX idx_arkana_dashboard_cells_order,
  DROP INDEX idx_arkana_dashboard_cells_prev;

ALTER TABLE arkana_report_cells
  ADD KEY idx_arkana_report_cells_arkana (arkana_object_id),
  ADD KEY idx_arkana_report_cells_order (arkana_object_id, run_order),
  ADD KEY idx_arkana_report_cells_prev (arkana_object_id, prev_id),
  ADD CONSTRAINT fk_arkana_report_cells_object
    FOREIGN KEY (arkana_object_id) REFERENCES arkana_object(arkana_id)
    ON DELETE CASCADE
    ON UPDATE CASCADE;
