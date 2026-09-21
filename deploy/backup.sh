#!/bin/sh
# Daily Postgres dump; keeps 14 days. Cron: 30 3 * * * /var/www/codearena-uz/deploy/backup.sh
set -e
cd "$(dirname "$0")/.."
mkdir -p /var/backups/codearena
docker compose exec -T db pg_dump -U codearena codearena | gzip > "/var/backups/codearena/db-$(date +%F).sql.gz"
find /var/backups/codearena -name "db-*.sql.gz" -mtime +14 -delete
