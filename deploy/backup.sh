#!/bin/sh
# Daily Postgres dump; keeps 14 days. Cron: 30 3 * * * /var/www/codearena-uz/deploy/backup.sh
set -e
cd "$(dirname "$0")/.."
mkdir -p /var/backups/codearena
docker compose exec -T db pg_dump -U codearena codearena | gzip > "/var/backups/codearena/db-$(date +%F).sql.gz"
find /var/backups/codearena -name "db-*.sql.gz" -mtime +14 -delete
# uploaded files (avatars, statement images) live in the `media` volume: archive them weekly
if [ "$(date +%u)" = "7" ]; then
  docker run --rm -v codearena-uz_media:/m:ro -v /var/backups/codearena:/b alpine tar czf "/b/media-$(date +%F).tgz" -C /m .
  find /var/backups/codearena -name "media-*.tgz" -mtime +28 -delete
fi
# off-site copy: set RCLONE_REMOTE (for example b2:codearena-backups) once rclone is configured on this host
if [ -n "$RCLONE_REMOTE" ] && command -v rclone >/dev/null 2>&1; then
  rclone copy /var/backups/codearena "$RCLONE_REMOTE" --max-age 2d
fi
