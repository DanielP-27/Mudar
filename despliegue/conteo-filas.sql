-- Número exacto de filas de cada tabla de la base, una por línea.
--
-- Sirve para «contrastar conteos conocidos» al verificar un respaldo
-- (CLAUDE.md 6.2): se ejecuta sobre la base viva y sobre la restaurada, y las
-- dos salidas tienen que ser idénticas.
--
--   sudo -u postgres psql -d mudar_db    -At -f conteo-filas.sql > /tmp/conteo_viva.txt
--   sudo -u postgres psql -d mudar_verif -At -f conteo-filas.sql > /tmp/conteo_verif.txt
--   diff /tmp/conteo_viva.txt /tmp/conteo_verif.txt
--
-- La lista de tablas sale del catálogo, así que una tabla nueva entra sola.
-- SQL no deja contar una tabla cuyo nombre solo se conoce al ejecutar:
-- query_to_xml ejecuta la consulta construida en ese momento y xpath extrae el
-- número. %I pone comillas al nombre cuando hace falta.
SELECT table_name,
       (xpath('/row/c/text()',
              query_to_xml(format('SELECT count(*) AS c FROM %I', table_name),
                           false, true, '')))[1]::text::int AS filas
FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
ORDER BY table_name;
