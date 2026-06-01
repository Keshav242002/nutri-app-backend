# NutriPlan — AWS EC2 + Docker Compose Deployment Guide

**Target:** Single EC2 t3.micro instance running all services via Docker Compose.  
**Architecture:** `caddy` (HTTPS) → `web` (gunicorn) + `worker` (celery) + `beat` (celery-beat) + `postgres` + `redis`

> **Railway / Render alternative:** These platforms are simpler if AWS becomes burdensome.
> Add a one-liner `Procfile` manually: `web: gunicorn nutriplan.wsgi --bind 0.0.0.0:$PORT --workers 2 --timeout 120`

---

## Step 1: Prerequisite — AWS Account & Free Tier

AWS changed their free tier on **July 15, 2025**:

| Account created | Model | What you get |
|----------------|-------|-------------|
| Before July 15, 2025 | Classic 12-month | 750 hrs/month t3.micro, 30 GB EBS, 5 GB S3 — for 12 months |
| After July 15, 2025 | Credit-based | $100–$200 in AWS credits, depletes as you spend |

Check your model at [AWS Billing Dashboard](https://console.aws.amazon.com/billing/) → Free Tier.

---

## Step 2: Billing Guardrails (DO THIS FIRST)

> ⚠️ Set up billing alarms **before** launching any EC2 instance. One forgotten NAT Gateway costs $32/month.

### 2.1 Create AWS Budgets

Go to [AWS Budgets](https://console.aws.amazon.com/billing/home#/budgets):

1. **Zero-spend alarm** — notifies on the very first charge
2. **$1 alarm** — 100% of $1
3. **$5 alarm** — 100% of $5
4. **$10 alarm** — 80% ($8) and 100% ($10)

Set all notifications to your email.

### 2.2 Enable Cost Explorer

[Cost Explorer](https://console.aws.amazon.com/cost-management/home#/cost-explorer) → Enable. Takes ~24h to populate.

### 2.3 Footguns to avoid

| Footgun | Cost | Prevention |
|---------|------|------------|
| NAT Gateway | ~$32/month | Do NOT create one. Your EC2 has a public IP and doesn't need it. |
| Unused Elastic IP | ~$3.60/month | Don't allocate unless needed. Release when done. |
| EBS volumes | $0.08/GB/month | Check "Delete on Termination" when launching. |
| Multiple instances | Multiplied | ONE instance in ONE region. |
| Public IPv4 (post Feb 2024) | $3.60/month | Free tier covers 750 hrs/month — one always-on t3.micro. |

---

## Step 3: EC2 Instance Setup

### 3.1 Launch the instance

1. [EC2 Console](https://console.aws.amazon.com/ec2/) → **Launch Instance**
2. **Name:** `nutriplan-backend`
3. **AMI:** Amazon Linux 2023 or Ubuntu 24.04 LTS (both free-tier eligible)
4. **Instance type:** `t3.micro`
5. **Key pair:** Create new → download `.pem` → `chmod 400 nutriplan-key.pem`
6. **Security group inbound rules:**

| Port | Source | Purpose |
|------|--------|---------|
| 22 | Your IP only | SSH (restrict — not 0.0.0.0/0) |
| 80 | 0.0.0.0/0 | HTTP |
| 443 | 0.0.0.0/0 | HTTPS |

7. **Storage:** 8 GB gp3, **Delete on Termination: checked**
8. Launch.

### 3.2 Connect via SSH

```bash
ssh -i nutriplan-key.pem ec2-user@<public-ip>   # Amazon Linux
ssh -i nutriplan-key.pem ubuntu@<public-ip>      # Ubuntu
```

> **Tip:** SSM Session Manager avoids exposing port 22. Attach `AmazonSSMManagedInstanceCore` IAM role → connect via AWS Console → EC2 → Connect → Session Manager.

### 3.3 Install Docker + Docker Compose

**Amazon Linux 2023:**
```bash
sudo dnf update -y
sudo dnf install -y docker git
sudo systemctl start docker && sudo systemctl enable docker
sudo usermod -aG docker ec2-user
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
exit  # log back in for group change
```

**Ubuntu 24.04:**
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io docker-compose-v2 git
sudo systemctl start docker && sudo systemctl enable docker
sudo usermod -aG docker ubuntu
exit  # log back in for group change
```

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
DJANGO_ALLOWED_HOSTS=<instance-public-dns>,<your-domain>,localhost

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

> ⚠️ Without backups, terminating the EC2 instance **permanently destroys all data**. Postgres runs in a Docker volume on the EBS root disk. There is no automated failover or PITR. Set this up before using real data.

### 5.1 Create S3 bucket

```bash
aws s3 mb s3://nutriplan-backups-<your-unique-suffix> --region <your-region>
```

S3 always-free tier: 5 GB storage, 2k PUT requests, 20k GET requests/month.

### 5.2 Configure AWS CLI on the instance

Use an IAM user with only `s3:PutObject` + `s3:GetObject` on the backup bucket:

```bash
aws configure   # enter Access Key, Secret Key, Region, json
```

### 5.3 Backup script

Create `~/backup-db.sh` on the EC2 instance:

```bash
#!/bin/bash
set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="/tmp/nutriplan_backup_${TIMESTAMP}.sql.gz"
S3_BUCKET="s3://nutriplan-backups-<your-suffix>"

docker compose -f ~/nutri-app-backend/docker-compose.yml \
  exec -T postgres pg_dump -U nutriplan nutriplan \
  | gzip > "${BACKUP_FILE}"

aws s3 cp "${BACKUP_FILE}" "${S3_BUCKET}/daily/${TIMESTAMP}.sql.gz"
find /tmp -name "nutriplan_backup_*.sql.gz" -mtime +7 -delete
echo "[$(date)] Backup complete: ${BACKUP_FILE}"
```

```bash
chmod +x ~/backup-db.sh
```

### 5.4 Schedule daily at 3 AM UTC

```bash
crontab -e
```

Add:
```
0 3 * * * /home/ec2-user/backup-db.sh >> /home/ec2-user/backup.log 2>&1
```

### 5.5 Restore from backup

```bash
aws s3 cp s3://nutriplan-backups-<suffix>/daily/<timestamp>.sql.gz /tmp/restore.sql.gz
docker compose stop web worker beat
gunzip -c /tmp/restore.sql.gz | docker compose exec -T postgres psql -U nutriplan nutriplan
docker compose start web worker beat
```

---

## Step 6: HTTPS / Domain

### Option A: Domain available (recommended) — Caddy

Point your domain's A record to the EC2 public IP. Edit `Caddyfile`:

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
| Billing alarm | [AWS Budgets console](https://console.aws.amazon.com/billing/home#/budgets) | Zero-spend + $1/$5/$10 alarms active |
| Backup cron | `crontab -l` | Backup script scheduled |
| Backup test | `~/backup-db.sh` | Backup appears in S3 |

---

## Step 8: Graduation Path (Future — Don't Build Now)

| Current | Upgrade to | Why |
|---------|-----------|-----|
| Postgres container on EC2 | **Amazon RDS** | Automated backups, Multi-AZ failover, managed patches |
| Redis container on EC2 | **Amazon ElastiCache** | Persistence, failover |
| Single EC2 | **ECS/Fargate** or Auto Scaling Group | Horizontal scaling, rolling deploys |
| Caddy on EC2 | **ALB + ACM** | Managed TLS, path-based routing, WAF |
| pg_dump cron | RDS automated snapshots | Continuous backup with PITR |

This is the spec's stated "move to AWS ECS at scale" moment — a deliberate future step, not an M8 task.
