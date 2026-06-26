# NutriPlan — GCP Compute Engine + Docker Compose Deployment Guide

**Target:** Single Compute Engine `e2-micro` instance running all services via Docker Compose.
**Architecture:** `caddy` (HTTPS) → `web` (gunicorn) + `worker` (celery) + `beat` (celery-beat) + `postgres` + `redis`

> **Cloud Run / Railway / Render alternative:** These are simpler if a single VM becomes burdensome.
> Cloud Run fits the `web` container well but is awkward for the always-on `worker`/`beat` and self-hosted
> `redis`/`postgres` — it needs Memorystore (no free tier) + Cloud SQL. For the free-tier MVP, the single
> e2-micro VM below maps the existing `docker-compose.yml` 1:1. A `Procfile` for PaaS:
> `web: gunicorn nutriplan.wsgi --bind 0.0.0.0:$PORT --workers 2 --timeout 120`

---

## Step 1: Prerequisite — GCP Account & Free Tier

GCP has two distinct free offers — you get both:

| Offer | What you get |
|-------|-------------|
| **90-day free trial** | $300 in credits, usable on anything (no charge until you manually upgrade) |
| **Always Free** (no expiry) | 1× `e2-micro` VM/month in `us-west1`, `us-central1`, or `us-east1`; 30 GB standard persistent disk; 5 GB regional Cloud Storage; 1 GB egress/month |

Check usage at the [Billing → Reports](https://console.cloud.google.com/billing) dashboard.

> ⚠️ The Always-Free `e2-micro` is **only** free in those three US regions. Launch anywhere else and it bills hourly.

---

## Step 2: Billing Guardrails (DO THIS FIRST)

> ⚠️ Set up budget alerts **before** launching any VM. One forgotten Cloud NAT or static IP quietly bills monthly.

### 2.1 Create a Cloud Billing Budget

Go to [Billing → Budgets & alerts](https://console.cloud.google.com/billing/budgets) → **Create budget**:

1. Scope it to your project.
2. Set **Target amount** = $1 (or $5/$10 for headroom).
3. Set threshold alerts at **50%, 90%, 100%** — and tick **Actual** and **Forecasted**.
4. Notifications go to the billing-account admins' email by default.

> Budgets only *notify*; they do not cap spend. To hard-stop, wire the budget's Pub/Sub topic to a Cloud Function that disables billing — optional, see graduation path.

### 2.2 Enable Billing Reports

[Billing → Reports](https://console.cloud.google.com/billing/reports) is on by default. Group by **Service** and **SKU** to spot surprises.

### 2.3 Footguns to avoid

| Footgun | Cost | Prevention |
|---------|------|------------|
| Cloud NAT | ~$32/month + data | Do NOT create one. Your VM has an external IP and doesn't need it. |
| Reserved static IP, **unattached** | ~$7/month | A static IP is free **while attached** to a running VM. Release it if you delete the VM. |
| Wrong region | Hourly billing | e2-micro is only Always-Free in `us-west1` / `us-central1` / `us-east1`. |
| Larger machine type | Multiplied | `e2-micro` only. `e2-small`/`e2-medium` are NOT free. |
| Persistent disk over 30 GB | $0.04/GB/month | Stay at ≤30 GB **standard** (pd-standard), not SSD (pd-ssd is not free). |
| Premium network tier egress | Per-GB | Default egress within free allowance is fine; large image/asset transfer is not. |

---

## Step 3: Compute Engine Instance Setup

### 3.1 Launch the instance

Console: [Compute Engine → VM instances](https://console.cloud.google.com/compute/instances) → **Create instance**. Or CLI:

```bash
gcloud compute instances create nutriplan-backend \
  --zone=us-central1-a \
  --machine-type=e2-micro \
  --image-family=debian-12 --image-project=debian-cloud \
  --boot-disk-size=30GB --boot-disk-type=pd-standard \
  --tags=http-server,https-server
```

- **Machine type:** `e2-micro` (Always-Free in the three US regions)
- **Image:** Debian 12 or Ubuntu 24.04 LTS
- **Boot disk:** 30 GB **pd-standard** (free-tier ceiling)
- **Network tags:** `http-server`, `https-server` apply GCP's built-in firewall rules for ports 80/443

### 3.2 Firewall rules

The `http-server` / `https-server` tags open 80/443 to `0.0.0.0/0`. SSH (22) is handled by `gcloud` over Google's infra — **do not** open 22 to the world. If you add a custom rule, restrict the source to your IP:

```bash
gcloud compute firewall-rules create allow-ssh-from-me \
  --allow=tcp:22 --source-ranges=<your.ip.addr>/32 --target-tags=nutriplan
```

### 3.3 Connect via SSH

```bash
gcloud compute ssh nutriplan-backend --zone=us-central1-a
```

> **Tip:** This uses OS Login / ephemeral keys managed by Google — no `.pem` file to guard, and port 22 need not be public. For agentless access use IAP TCP forwarding: add `--tunnel-through-iap`.

### 3.4 Install Docker + Docker Compose

**Debian 12 / Ubuntu 24.04:**
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io docker-compose-v2 git
sudo systemctl start docker && sudo systemctl enable docker
sudo usermod -aG docker "$USER"
exit  # log back in for the group change to take effect
```

> ⚠️ **Memory:** `e2-micro` has only **1 GB RAM** for postgres + redis + gunicorn + worker + beat + caddy. Add swap so the OOM killer doesn't reap Celery:
> ```bash
> sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
> sudo mkswap /swapfile && sudo swapon /swapfile
> echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
> ```

---

## Step 4: Deploy the Stack

### 4.1 Clone the repository

```bash
cd ~
git clone https://github.com/Keshav242002/nutri-app-backend.git
cd nutri-app-backend
```

### 4.2 Create production `.env`

```bash
cp .env.example .env
nano .env
```

> ⚠️ Never commit this file. `.gitignore` already excludes it.

**Required values:**

```bash
# Django
DJANGO_SECRET_KEY=<generate: python -c "import secrets; print(secrets.token_urlsafe(50))">
DJANGO_DEBUG=False
DJANGO_SETTINGS_MODULE=nutriplan.settings.production
DJANGO_ALLOWED_HOSTS=<instance-external-ip>,<your-domain>,localhost

# Database — use Docker service name, not localhost
DATABASE_URL=postgres://nutriplan:nutriplan@postgres:5432/nutriplan

# Redis — use Docker service name, not localhost
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

# Firebase Auth — paste entire JSON as one line (no file needed in container)
FIREBASE_CREDENTIALS_PATH=
FIREBASE_CREDENTIALS_JSON=<paste firebase-admin.json content here as one line>

# LLM Provider
AI_PROVIDER=gemini_native
LLM_TIMEOUT_SECONDS=30
GEMINI_API_KEY=<your-key>
GEMINI_MODEL=gemini-2.5-flash

# USDA
USDA_API_KEY=<your-key>
USDA_BASE_URL=https://api.nal.usda.gov/fdc/v1

# CORS
CORS_ALLOWED_ORIGINS=<your Flutter app origins, comma-separated>

# Rate limits
REGENERATE_RATE_LIMIT=3/d
CHAT_RATE_LIMIT=30/h

# Sentry (optional)
SENTRY_DSN=

# DO NOT ADD DEV_AUTH_BYPASS_ENABLED — it is hard-coded False in production.py
```

### 4.3 First-run: build + migrate + seed

```bash
docker compose build

# Run migrate explicitly first to watch for errors
docker compose run --rm web python manage.py migrate --noinput

# Seed the recipe database (idempotent — safe to re-run)
docker compose run --rm web python manage.py seed_recipes

# Collect static files for admin panel
docker compose run --rm web python manage.py collectstatic --noinput
```

### 4.4 Start all services

```bash
docker compose up -d
```

The `web` service entrypoint (`docker-entrypoint.sh`) also runs migrate + seed + collectstatic on each start. `worker` and `beat` skip the entrypoint and run their Celery commands directly — they do NOT run migrations.

### 4.5 Verify

```bash
curl http://localhost:8000/healthz          # direct: {"status":"ok","db":"ok"}
curl http://localhost/healthz               # via Caddy reverse proxy
docker compose ps                           # all services should be "running"
docker compose logs web --tail=50
docker compose logs worker --tail=20
```

---

## Step 5: Database Backup (REQUIRED)

> ⚠️ Without backups, deleting the VM **permanently destroys all data**. Postgres runs in a Docker volume on the persistent disk. There is no automated failover or PITR. Set this up before using real data.

### 5.1 Create a Cloud Storage bucket

```bash
gcloud storage buckets create gs://nutriplan-backups-<your-unique-suffix> \
  --location=US --uniform-bucket-level-access
```

Always-Free Cloud Storage: 5 GB regional storage (`us-west1`/`us-central1`/`us-east1`), 5k Class A + 50k Class B ops/month. Keep the bucket in a free-tier region.

### 5.2 Grant the VM's service account write access — **no keys needed**

The VM runs as a service account (the Compute Engine default SA unless you set one). Grant it object access on the backup bucket; the `gcloud`/`gsutil` already on the VM authenticate automatically via the metadata server — there is **no `aws configure` equivalent and no key file to leak**.

```bash
# Find the VM's service account email
gcloud compute instances describe nutriplan-backend --zone=us-central1-a \
  --format='value(serviceAccounts.email)'

# Grant least-privilege write on just this bucket
gcloud storage buckets add-iam-policy-binding gs://nutriplan-backups-<suffix> \
  --member="serviceAccount:<vm-sa-email>" --role=roles/storage.objectAdmin
```

> If the default SA's scopes are restricted, recreate the VM with `--scopes=storage-rw`, or attach a dedicated SA at create time.

### 5.3 Backup script

Create `~/backup-db.sh` on the VM:

```bash
#!/bin/bash
set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="/tmp/nutriplan_backup_${TIMESTAMP}.sql.gz"
GCS_BUCKET="gs://nutriplan-backups-<your-suffix>"

docker compose -f ~/nutri-app-backend/docker-compose.yml \
  exec -T postgres pg_dump -U nutriplan nutriplan \
  | gzip > "${BACKUP_FILE}"

gcloud storage cp "${BACKUP_FILE}" "${GCS_BUCKET}/daily/${TIMESTAMP}.sql.gz"
find /tmp -name "nutriplan_backup_*.sql.gz" -mtime +7 -delete
echo "[$(date)] Backup complete: ${BACKUP_FILE}"
```

```bash
chmod +x ~/backup-db.sh
```

> Set a bucket lifecycle rule to auto-delete objects older than 30 days so you stay under 5 GB:
> `gcloud storage buckets update gs://nutriplan-backups-<suffix> --lifecycle-file=lifecycle.json`

### 5.4 Schedule daily at 3 AM UTC

```bash
crontab -e
```

Add:
```
0 3 * * * /home/<your-user>/backup-db.sh >> /home/<your-user>/backup.log 2>&1
```

### 5.5 Restore from backup

```bash
gcloud storage cp gs://nutriplan-backups-<suffix>/daily/<timestamp>.sql.gz /tmp/restore.sql.gz
docker compose stop web worker beat
gunzip -c /tmp/restore.sql.gz | docker compose exec -T postgres psql -U nutriplan nutriplan
docker compose start web worker beat
```

---

## Step 6: HTTPS / Domain

### Option A: Domain available (recommended) — Caddy

Reserve a static external IP and attach it to the VM (free while attached), then point your domain's A record at it. Edit `Caddyfile`:

```
your-domain.com {
    reverse_proxy web:8000
}
```

Caddy handles TLS certificate issuance and renewal automatically.

### Option B: No domain — HTTP only (MVP acceptable)

Switch the reverse proxy in `docker-compose.yml` from `caddy` to `nginx`:

```yaml
nginx:
  image: nginx:alpine
  restart: unless-stopped
  ports:
    - "80:80"
  volumes:
    - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
  depends_on:
    - web
```

And in production `.env` add:
```bash
SECURE_SSL_REDIRECT=False
```

> ⚠️ Firebase auth tokens travel over unencrypted HTTP. Acceptable for dev/MVP; not for real users.

---

## Step 7: Post-Deploy Verification Checklist

| Check | Command / Action | Expected |
|-------|-----------------|----------|
| Health check | `curl http://<ip>/healthz` | `{"status":"ok","db":"ok"}` |
| API docs | `http://<ip>/api/docs/` in browser | Swagger UI, all endpoints visible |
| Auth flow | `POST /api/v1/auth/register` with Firebase token | 200 |
| Onboarding | `POST /api/v1/profiles/onboarding` | 200 with computed targets |
| Today's plan | `GET /api/v1/mealplans/today/` | 200 with breakfast/lunch/dinner |
| Celery worker | `docker compose logs worker` | "celery@... ready" |
| Beat scheduler | `docker compose logs beat` | "beat: Starting..." |
| Beat single replica | `docker compose ps beat` | Exactly ONE beat container |
| Rate limit | POST /auth/register 11× rapidly | 11th returns 429 RATE_LIMITED |
| Budget alert | [Billing → Budgets](https://console.cloud.google.com/billing/budgets) | Budget with 50/90/100% alerts active |
| Backup cron | `crontab -l` | Backup script scheduled |
| Backup test | `~/backup-db.sh` | Backup appears in the GCS bucket |

---

## Step 8: Graduation Path (Future — Don't Build Now)

| Current | Upgrade to | Why |
|---------|-----------|-----|
| Postgres container on the VM | **Cloud SQL for PostgreSQL** | Automated backups, HA failover, managed patches, PITR |
| Redis container on the VM | **Memorystore for Redis** | Persistence, failover |
| Single e2-micro VM | **Cloud Run** (web) + **GKE Autopilot** (worker/beat) | Horizontal scaling, rolling deploys, scale-to-zero |
| Caddy on the VM | **External HTTPS Load Balancer + Google-managed certs** | Managed TLS, path routing, Cloud Armor (WAF) |
| pg_dump cron | Cloud SQL automated backups | Continuous backup with PITR |
| Manual `gcloud` deploys | **Cloud Build + Artifact Registry** | CI/CD image build + push on commit |

This is the "move to managed GCP services at scale" moment — a deliberate future step, not an M8 task.
