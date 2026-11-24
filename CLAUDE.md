# SecurePay Project Guide

This file is the project handoff and operating guide for contributors and AI coding assistants. Treat repository code and Kubernetes manifests as the implementation source of truth. Do not assume a deployment is healthy without checking it.

## Project purpose

SecurePay is a Django freelance marketplace demo for a college project. It supports clients and freelancers managing gigs, contracts, milestone submissions, simulated escrow/payment records, disputes, messaging, reviews, invoices, notifications, dashboards, and fraud signals. It does **not** collect card data or move real money. Never add live payment credentials or describe the demo ledger as real escrow.

The project USP is the **Verifiable Work Ledger**: contract proposals fingerprint the agreed parties, scope, terms, total, and ordered milestones; acceptance anchors the fingerprint in a SHA-256 hash-chained activity log. Contract participants can view verification and download a JSON evidence record. This is tamper-evident, not a digital signature or an independent timestamp; an administrator able to rewrite the database can recompute the chain.

## Technology and services

- Python 3.12, Django, Django REST Framework, PostgreSQL, JWT.
- Celery worker and beat, Redis broker.
- Docker / Docker Compose for local full-stack operation and CI.
- Jenkins pipeline runs checks/tests, builds a local image, and deploys to kind. No registry push is configured.
- Kubernetes manifests are under `k8s/`; Postman collection is under `postman/`.
- Payments are simulated internal records only. The app is a local college demo, not a production financial service.

## App map

| Django app | Responsibility |
| --- | --- |
| `accounts` | Registration, login, email verification, password recovery, account/profile and roles |
| `marketplace` | Gigs and discovery |
| `contracts` | Proposals, agreements, milestones and contract evidence ledger |
| `payments` | Simulated funding/release/payment records |
| `disputes` | Dispute filing and staff resolution |
| `messaging` | Contract/client-freelancer messages |
| `reviews` | Post-contract reviews |
| `invoices` | Invoice records and presentation |
| `notifications` | Notification delivery and scheduled deadline reminders |
| `fraud` | Risk signals / fraud flags |
| `auditlog` | Hash-chained audit events and verification |
| `api` | DRF API serializers, views and routes |
| `core` | Shared utilities and shared UI/health functionality |
| `config` | Django settings, root URLs and Celery setup |

Keep business rules in service/model layers rather than duplicating them in views. Enforce authentication, role checks and object ownership on every private endpoint. Preserve the demo-only nature of payment operations.

## Secrets and environment

- `.env` and secret values must never be committed, pasted into chat, or included in a distributable ZIP.
- `.env.example` is a template, not a source of real credentials. The Django application does not automatically load `.env` for bare `runserver`; export variables in the shell or use Compose `env_file`.
- Compose requires `DJANGO_SECRET_KEY` and `DB_PASSWORD`. Use long, unique random values for local environments.
- Kubernetes uses Secret `securepay-secrets` in namespace `securepay`, with keys `DJANGO_SECRET_KEY`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD`. The Secret is created once per cluster and is intentionally not in Git.
- Never print secret contents. `kubectl describe secret` lists key names and sizes without revealing values.
- Local kind configuration uses HTTP through localhost port-forwarding, so its ConfigMap disables HTTPS redirect and secure cookies. Do not copy that profile to a public deployment.

## Local development

From Ubuntu on WSL, in `/mnt/d/Devops-projects/SecurePay`:

```bash
python3.12 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
export DJANGO_SECRET_KEY="$(openssl rand -hex 48)"
export DB_ENGINE=sqlite
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

The local web-only setup uses SQLite. For the complete app stack, prepare `.env` from `.env.example`, set private values, then:

```bash
docker compose up --build -d
docker compose ps
docker compose logs --tail=100 web celery-worker celery-beat
```

Open `http://localhost:8000`. Stop Compose with `docker compose down`; this preserves named volumes. `docker compose down -v` deletes local database/media data and should only be used intentionally.

## Checks and API use

Run project checks when asked to verify changes:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

Compose CI suite (PostgreSQL-backed):

```bash
docker compose -f docker-compose.ci.yml up --build --abort-on-container-exit --exit-code-from tests tests
docker compose -f docker-compose.ci.yml down --remove-orphans
```

API base is `/api/v1/`. JWT login is `POST /api/v1/auth/token/` with email/password; send `Authorization: Bearer <access>` for protected requests. Access JWT lifetime is 15 minutes; refresh is one day and rotates/blacklists. Registration requires email verification. Public gigs and registration are unauthenticated. See `postman/SecurePay.postman_collection.json`; configure `baseUrl` and `accessToken` there. Example routes include gigs, contracts, milestone fund/submit/release, disputes, and invoices. Refer to the collection for exact methods and payloads.

## DevOps: Docker, Jenkins, and kind

### Separation rule

SecurePay belongs in kind cluster `securepay`, context `kind-securepay`, namespace `securepay`. InfraFlow is a separate project and cluster `infraflow`. Never deploy SecurePay using the current context without checking it; the Jenkinsfile explicitly selects `kind-securepay`. Do not delete/modify InfraFlow resources as part of SecurePay work.

Current environment facts last confirmed during setup: SecurePay kind cluster was created as a single-node Kubernetes `v1.36.1` cluster; its default `standard` StorageClass is backed by kind's local-path provisioner. Namespace and generated Secret were created. Jenkins user's kubeconfig was verified to show `kind-securepay` and a Ready `securepay-control-plane`. Commit `86f165d` contains the dedicated-cluster configuration. The latest Jenkins deployment result was not confirmed in the handoff; verify it before claiming the app is deployed. InfraFlow node containers were temporarily stopped to free resources; check their current state before restarting/stopping anything.

### Verify host tools and cluster

```bash
cd /mnt/d/Devops-projects/SecurePay
git status --short
git log -1 --oneline
docker version
docker ps -a
kind get clusters
kubectl config get-contexts
kubectl config use-context kind-securepay
kubectl config current-context
kubectl get nodes -o wide
kubectl get storageclass
kubectl get pods -n local-path-storage
```

Expected SecurePay context is `kind-securepay`; its control-plane node should be Ready, the `standard` StorageClass should exist, and local-path-provisioner should be Running.

### Jenkins

The Jenkins job's pipeline stages are: checkout; PostgreSQL-backed system/migration/test checks; build `securepay:${BUILD_NUMBER}`; load image into kind cluster `securepay`; apply database and Redis; run migration Job; apply and wait for web, worker, and beat. It does not push to a registry. Jenkins Linux agent needs Git, Docker, Compose, `kind`, `kubectl`, Docker access, and the SecurePay kubeconfig. The one-time Kubernetes Secret must exist before deploy.

Check Jenkins service and build in WSL / browser:

```bash
sudo systemctl status jenkins --no-pager
sudo -u jenkins kubectl config current-context
sudo -u jenkins kubectl get nodes
sudo -u jenkins kind get clusters
```

Expected Jenkins context is `kind-securepay`; cluster list must include `securepay`. In Jenkins UI, run **Build Now**, then inspect Console Output and require `Finished: SUCCESS` and successful test/deploy stages.

To refresh Jenkins kubeconfig after changing/creating the SecurePay cluster, first select and verify the user context:

```bash
kubectl config use-context kind-securepay
kubectl config current-context
sudo install -d -o jenkins -g jenkins -m 700 /var/lib/jenkins/.kube
umask 077
kubectl config view --minify --raw > /tmp/securepay-kubeconfig
sudo install -o jenkins -g jenkins -m 600 /tmp/securepay-kubeconfig /var/lib/jenkins/.kube/config
rm /tmp/securepay-kubeconfig
sudo -u jenkins kubectl config current-context
sudo -u jenkins kubectl get nodes
```

`sudo` may prompt for the user's Ubuntu password. Never share the kubeconfig file; it contains cluster credentials.

### Manual kind bootstrap (only if rebuilding the dedicated cluster)

This deletes the SecurePay kind cluster and its demo data. Use only when intentionally rebuilding it. First verify the context/cluster names and ensure no SecurePay data needs retention. Do not delete `infraflow`.

```bash
kind create cluster --name securepay --image kindest/node:v1.36.1 --wait 5m
kubectl config use-context kind-securepay
kubectl get nodes
kubectl get storageclass
kubectl apply -f k8s/namespace.yaml
kubectl -n securepay create secret generic securepay-secrets \
  --from-literal=DJANGO_SECRET_KEY="$(openssl rand -hex 48)" \
  --from-literal=DB_NAME=securepay \
  --from-literal=DB_USER=securepay \
  --from-literal=DB_PASSWORD="$(openssl rand -hex 24)"
```

If deploying manually rather than Jenkins, from the repo root:

```bash
docker build -t securepay:dev .
kind load docker-image securepay:dev --name securepay
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/redis.yaml
kubectl -n securepay rollout status statefulset/securepay-db --timeout=300s
kubectl -n securepay rollout status deployment/securepay-redis --timeout=180s
kubectl apply -f k8s/migration-job.yaml
kubectl -n securepay wait --for=condition=complete job/securepay-migrate --timeout=300s
kubectl apply -f k8s/app.yaml
kubectl -n securepay rollout status deployment/securepay-web --timeout=240s
kubectl -n securepay rollout status deployment/securepay-worker --timeout=180s
kubectl -n securepay rollout status deployment/securepay-beat --timeout=180s
```

Avoid manually applying a `securepay:dev` image after a Jenkins deployment unless that is intentional; it can replace the build-number-tagged image.

### Deployment verification and site access

```bash
kubectl config use-context kind-securepay
kubectl -n securepay get deployments,statefulsets,pods,services,jobs,pvc -o wide
kubectl -n securepay get events --sort-by=.lastTimestamp
kubectl -n securepay logs deployment/securepay-web --tail=100
kubectl -n securepay logs deployment/securepay-worker --tail=100
kubectl -n securepay logs deployment/securepay-beat --tail=100
kubectl -n securepay logs statefulset/securepay-db --tail=100
kubectl -n securepay logs deployment/securepay-redis --tail=100
```

Expected: web/worker/beat/Redis are Available/Ready; DB StatefulSet is Ready; migration Job is Complete; PVCs are Bound. Do not share logs containing credentials or user data.

In one WSL terminal, keep this running:

```bash
kubectl -n securepay port-forward service/securepay-web 8000:8000
```

In another WSL terminal:

```bash
curl -i http://localhost:8000/healthz/
```

Open `http://localhost:8000` in the browser. The port-forward stops when its terminal exits.

### Routine cluster controls

```bash
# SecurePay: verify/select
kubectl config use-context kind-securepay
kubectl get nodes

# InfraFlow: only when the user wants it running; containers/data are preserved
docker start infraflow-control-plane infraflow-worker
kubectl config use-context kind-infraflow
kubectl wait --for=condition=Ready nodes --all --timeout=180s
kubectl get nodes
kubectl -n infraflow get pods

# Stop InfraFlow to reduce resource load while presenting SecurePay
docker stop infraflow-control-plane infraflow-worker
```

Starting/stopping a kind cluster container does not delete its data. Two clusters may compete for WSL CPU/RAM; this machine previously showed high CPU use while InfraFlow ran, and SecurePay cluster creation only succeeded after InfraFlow was stopped. For an InfraFlow browser session, use `kubectl -n infraflow port-forward service/nginx-service 8081:80` and open `http://localhost:8081`.

### Where commands must run (common cause of "kubectl is broken")

The `kind-securepay` context, the Jenkins service and the kind node containers live inside **Ubuntu on WSL 2** (Docker Engine there). Windows PowerShell/Git Bash have their own Docker Desktop `kubectl`, which only knows the `docker-desktop` context and will not see `kind-securepay`. Run every `kubectl`/`kind`/`docker` command from the Ubuntu WSL terminal. Before anything else check that WSL and Docker are actually up: `wsl -l -v` (Ubuntu must be Running), then `docker ps -a` inside Ubuntu. If Docker/WSL is stopped, the kind node containers are stopped too and `kubectl` fails with connection refused / TLS errors; start them with `docker start securepay-control-plane` (cluster `securepay`) and wait for `kubectl get nodes` to show Ready. Keep `kubectl` within one minor version of the cluster (v1.36); Docker Desktop's bundled client was v1.34, which is outside the supported skew.

The project folder may exist both at `C:\Users\Saarvi\Desktop\SecurePay\SecurePay` (Windows) and `/mnt/d/Devops-projects/SecurePay` (WSL, used by Jenkins). Confirm which copy you are editing; the Jenkins job builds from Git, so commit and push changes rather than relying on file edits in a different copy.

### Troubleshooting quick checks

```bash
free -h
docker stats --no-stream
docker ps -a
kubectl config current-context
kubectl get nodes
kubectl -n securepay describe pod <pod-name>
kubectl -n securepay get events --sort-by=.lastTimestamp
kubectl -n securepay describe pvc <pvc-name>
```

- `ImagePullBackOff`: Jenkins should load the locally built image into the `securepay` kind cluster; check Jenkins output and `kind get clusters`.
- `Pending` PVC: verify `standard` StorageClass and local-path-provisioner pod.
- DB/web readiness failure: inspect pod events and logs; do not delete PVCs or rotate DB password casually.
- Namespace `Terminating`: inspect remaining resources/finalizers and events; never remove finalizers blindly.
- `kubectl` points to the wrong cluster: stop and explicitly select `kind-securepay` before any SecurePay operation.
- API server refuses connections during cluster creation: check `free -h` and `docker stats --no-stream`; avoid running both high-load clusters concurrently.

## Safe ZIP packaging

Include source, migration files, static/templates, `requirements.txt`, Docker/Compose files, `Jenkinsfile`, `k8s/`, Postman collection, README and this guide. Exclude secrets and machine/local state:

- `.env`, `.git/`, `venv/`, `__pycache__/`, `*.pyc`, `db.sqlite3`, local uploads/media, test artifacts, and editor/OS caches.
- Keep `.env.example` only if it contains placeholders and no credentials.
- Do not include Kubernetes Secret YAML or a kubeconfig. Current Kubernetes secret values are stored in the cluster, not in this repo.

Before creating a ZIP, inspect its file list and confirm there is no `.env`, database dump, private media, kubeconfig, token, or password. Do not run `git add .` when preparing a commit if `.env.example` or local state has unexpected modifications; stage named files.

## Payment, security, and deployment boundaries

- Funding/release endpoints update simulated internal records only. No real card, bank, Stripe, or escrow transfer exists.
- Dispute resolution is staff-only. Verify participant ownership and role permissions for every contract, milestone, message, invoice, dispute, and evidence endpoint.
- Email verification and password reset use expiring/one-time links; development email uses console output. Configure a real mail provider before relying on delivery.
- Deadline emails are disabled by default; Celery beat schedules reminders daily at 09:00 in `DJANGO_TIME_ZONE`.
- Hash chaining reveals altered history only when compared to a trusted retained anchor/export; it is not immutable storage.
- Public deployment needs separate production review: HTTPS/TLS, secure cookies/HSTS, restrictive allowed hosts, real email, managed secrets, database backups, private media storage, monitoring, and operational recovery procedures. The local kind profile is not production-ready.
