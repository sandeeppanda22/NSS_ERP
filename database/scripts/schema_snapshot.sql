-- One line per table of schema nss: name | columns | constraints | indexes | triggers.
-- Used by 02_build.sh / 02_build.ps1 / render_build.sh: the build takes it before and after its phases, and the build summary compares the
-- two (tables created, tables already present, tables altered). Read-only; run as `psql -qAtX -F '|' -f schema_snapshot.sql`.
SELECT c.relname,
       (SELECT COUNT(*) FROM pg_attribute a WHERE a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped),
       (SELECT COUNT(*) FROM pg_constraint k WHERE k.conrelid = c.oid),
       (SELECT COUNT(*) FROM pg_index i WHERE i.indrelid = c.oid),
       (SELECT COUNT(*) FROM pg_trigger t WHERE t.tgrelid = c.oid AND NOT t.tgisinternal)
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'nss' AND c.relkind IN ('r', 'p')
 ORDER BY c.relname;
