#!/bin/bash
# Respaldo nocturno de la base de MUDAR.
#
# Se instala en /usr/local/sbin/mudar-respaldo (root:root 755) y lo ejecuta
# mudar-respaldo.service como el usuario postgres, que entra a PostgreSQL por
# el socket local (peer) sin contraseña.
#
# Cada ejecución deja una carpeta /srv/respaldo/AAAA-MM-DD_HHMM con tres piezas:
#   globales.sql    roles y sus contraseñas (hashes): pieza 1 de CLAUDE.md 6.2.
#                   Se restaura PRIMERO, o el volcado falla por dueño inexistente.
#   mudar_db.dump   la base, en formato custom: pieza 2.
#   commit.txt      el commit del código que corría: sin él no se sabe con qué
#                   versión encaja el volcado.

# -e: se detiene en el primer error. -u: una variable sin definir es un error.
# -o pipefail: un fallo en medio de una tubería también cuenta.
set -euo pipefail

# Todo lo que se cree aquí nace 700 (carpetas) y 600 (archivos): contiene los
# hashes de las contraseñas.
umask 077

DESTINO=/srv/respaldo
BASE=mudar_db
RETENCION_DIAS=14

MARCA=$(date +%Y-%m-%d_%H%M)
FINAL="$DESTINO/$MARCA"
# Se escribe en una carpeta .incompleto y solo se renombra al final. Si algo
# falla a mitad, no queda una carpeta con nombre de respaldo válido que en
# realidad está a medias.
TEMPORAL="$FINAL.incompleto"

mkdir "$TEMPORAL"

pg_dumpall --globals-only --file="$TEMPORAL/globales.sql"
pg_dump --format=custom --file="$TEMPORAL/$BASE.dump" "$BASE"

# /opt/mudar es de root y esto corre como postgres: git se niega a leer un
# repositorio ajeno ("dubious ownership"). safe.directory lo autoriza solo para
# esta orden, sin tocar ninguna configuración. Si falla, el respaldo NO se
# pierde por ello: el volcado es lo valioso, y su tabla django_migrations
# permite reconstruir la versión.
if ! git -c safe.directory=/opt/mudar -C /opt/mudar rev-parse HEAD > "$TEMPORAL/commit.txt"; then
    echo "desconocido" > "$TEMPORAL/commit.txt"
    echo "AVISO: no se pudo leer el commit de /opt/mudar" >&2
fi

# Comprobación mínima: el volcado se puede leer. No prueba que se restaure;
# eso solo lo prueba una restauración (paso 14.5 del runbook).
pg_restore --list "$TEMPORAL/$BASE.dump" > /dev/null

mv "$TEMPORAL" "$FINAL"

# Retención: borra las carpetas de 14 días o más, incluidas las .incompleto
# que hayan quedado de un fallo. -name '20*' limita el borrado a carpetas con
# nombre de fecha: nada más de /srv/respaldo puede caer por error. El -- impide
# que un nombre raro se lea como opción de rm.
find "$DESTINO" -mindepth 1 -maxdepth 1 -type d -name '20*' \
    -mtime +$((RETENCION_DIAS - 1)) -exec rm -rf -- {} +

echo "Respaldo completo: $FINAL ($(du -sh "$FINAL" | cut -f1))"
