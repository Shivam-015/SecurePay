#!/bin/sh
# Start command for the Render web service (see render.yaml).
# Runs migrations, static collection, optional one-time setup, optional Celery,
# then gunicorn bound to the port Render provides.
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput

# Optional first admin account. Set DJANGO_SUPERUSER_EMAIL, DJANGO_SUPERUSER_PASSWORD
# and DJANGO_SUPERUSER_DISPLAY_NAME in the Render dashboard (never in Git).
# An existing account is left alone.
if [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ] && [ -n "${DJANGO_SUPERUSER_EMAIL:-}" ]; then
  python manage.py createsuperuser --noinput || echo "Superuser already exists or could not be created; continuing."
fi

# Optional demo data (idempotent). Set SEED_DEMO=true for the first deploy, then remove it.
if [ "${SEED_DEMO:-false}" = "true" ]; then
  python manage.py shell < scripts/seed_demo.py || echo "Demo seed failed; continuing."
fi

# Celery worker and beat share this container so the demo fits one free service.
if [ "${RUN_CELERY:-false}" = "true" ]; then
  celery -A config worker -B --loglevel=info --concurrency=1 --schedule=/tmp/celerybeat-schedule &
fi

exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 2 --timeout 60
