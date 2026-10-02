#!/bin/sh
set -e

mkdir -p "$(dirname "${DATABASE_PATH:-data/factchecker.db}")"
chown -R app:app "$(dirname "${DATABASE_PATH:-data/factchecker.db}")"
exec setpriv --reuid=app --regid=app --init-groups "$@"
