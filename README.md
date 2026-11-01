# SecurePay

SecurePay is a Django freelance marketplace with contract milestones, a **simulated college-project payment workflow**, dispute review, messaging, invoices, notifications, and an authenticated REST API. No card details or real money are collected or transferred.

## Local development (SQLite)

1. Create and activate a Python 3.12 virtual environment.
2. Install dependencies: `python -m pip install -r requirements.txt`.
3. Set `DJANGO_SECRET_KEY` and `DB_ENGINE=sqlite` in your shell before starting Django. Django does not load `.env` files by itself. For PowerShell, set them with `$env:DJANGO_SECRET_KEY='your-private-key'` and `$env:DB_ENGINE='sqlite'`. Keep `.env` out of source control.
4. Run `python manage.py migrate` and `python manage.py createsuperuser`.
5. Start the site with `python manage.py runserver`.

SQLite is the default for the local web-only flow. Deadline reminders need Redis and Celery worker/beat processes; use Compose below for all services.

## Full stack with Docker Compose

With Docker Engine and the Compose plugin available in Ubuntu on WSL, copy `.env.example` to `.env`, set a random Django secret and a unique database password, then run `docker compose up --build -d` from the project directory. Docker Desktop is not required when the WSL Engine is running and reachable by the `docker` CLI. The application image runs as a non-root user, the database password has no fallback, and Compose waits for the web readiness check before starting Celery. The web container applies migrations and collects static assets on startup. Open `http://localhost:8000`; create a staff user with `docker compose exec web python manage.py createsuperuser`.

Compose starts PostgreSQL, Redis, Django/Gunicorn, a Celery worker, and Celery beat. Only the web port is published, bound to `127.0.0.1` by default; PostgreSQL and Redis remain on the internal Compose network. `/healthz/` checks database readiness. For a public deployment, set `DJANGO_DEBUG=false`, a strong secret, correct `DJANGO_ALLOWED_HOSTS`, TLS and production email settings. Never expose the local secrets or database directly to the internet. Database backups and private submission file storage must be configured for any hosted deployment. Production HTTPS and HSTS settings are enabled when `DJANGO_DEBUG=false`; only disable `DJANGO_SECURE_SSL_REDIRECT` for local HTTP testing.

## Jenkins continuous integration

The `Jenkinsfile` runs the checks and test suite against a temporary PostgreSQL service, then builds a local image tagged with the Jenkins build number. It does not publish images or deploy. The Jenkins Linux agent needs Git, Docker Engine, and the Docker Compose plugin. Run the same CI checks locally with `docker compose -f docker-compose.ci.yml up --build --abort-on-container-exit --exit-code-from tests tests`, then clean up with `docker compose -f docker-compose.ci.yml down --remove-orphans`.

## API

Base URL: `/api/v1/`. Obtain a JWT by posting `{"email":"...","password":"..."}` to `/api/v1/auth/token/`; send `Authorization: Bearer <access>` for protected requests. Access tokens last 15 minutes; rotating refresh tokens last one day and are blacklisted after rotation. Public gig listing and registration do not require a token. API registration accepts `email`, `display_name`, `role` (`client` or `freelancer`), and `password`; the account stays inactive until its email is verified through `POST /auth/verify-email/` with the emailed token. `POST /auth/verify-email/resend/` safely requests another link.

The Postman collection is `postman/SecurePay.postman_collection.json`. Set its `baseUrl`, and set `accessToken` after logging in. Example endpoints include `/gigs/`, `/contracts/`, `/milestones/{id}/fund/`, `/milestones/{id}/submit/`, `/milestones/{id}/release/`, `/disputes/`, and `/invoices/`. See collection descriptions for method and demo workflow notes.

## Verifiable Work Ledger (project USP)

Each new contract proposal fingerprints the agreed parties, scope, terms, total, and ordered milestone plan. Acceptance records that same fingerprint in the contract's SHA-256 chained activity log. Either contract participant can review the verification result on the contract page or download a JSON evidence record from `GET /contracts/<id>/evidence.json`; API clients can use `GET /api/v1/contracts/<id>/evidence/`. The export includes the agreement snapshot, milestone plan, event sequence, event hashes, and a verification result. It omits account email addresses and message bodies. Legacy records without an agreement fingerprint are marked `unanchored`.

This is tamper-evident evidence, not a digital signature or independent timestamp: a database administrator who can rewrite the full chain can recompute hashes. Participants should retain exported records if they need to compare the history later.

Account recovery uses Django's one-time password reset tokens, and new accounts require a signed, expiring email verification link. The development email backend writes links to the server console; a real email provider must be configured before relying on email delivery.

All fund/release endpoints only create/update internal demo records. A dispute can only be resolved by staff. The deadline reminder task runs daily at 09:00 in `DJANGO_TIME_ZONE`; email is disabled unless `DEADLINE_EMAILS=true` and a real email backend is configured.

## Checks

Run `python manage.py check`, `python manage.py makemigrations --check --dry-run`, and `python manage.py test`. For Compose, `docker compose config` validates the service configuration. Test reminders locally with `python manage.py shell -c "from notifications.tasks import send_milestone_deadline_reminders; print(send_milestone_deadline_reminders())"` while Redis/Celery dependencies are installed.
