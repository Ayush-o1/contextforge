# ContextForge — Deployment Guide

> Deploy ContextForge to Railway (recommended for MVP) or any Docker-compatible platform.

---

## Railway Deployment (Recommended)

Railway provides a free tier with $5/month of usage credits. ContextForge fits within this budget for moderate usage.

### Prerequisites

- [Railway CLI](https://docs.railway.app/develop/cli) installed (`npm i -g @railway/cli`)
- [Railway account](https://railway.app/) (free tier available)
- Your `OPENAI_API_KEY`

### Step-by-Step Deployment

```bash
# 1. Login to Railway
railway login

# 2. Initialize project in the repository
cd contextforge
railway init

# 3. Provision Redis plugin (managed by Railway — no config needed)
railway add --plugin redis

# 4. Set environment variables
railway variables set OPENAI_API_KEY=sk-your-key-here
railway variables set REDIS_URL=\${{Redis.REDIS_URL}}
railway variables set SIMILARITY_THRESHOLD=0.92
railway variables set CACHE_TTL_SECONDS=86400
railway variables set PREFERRED_PROVIDER=openai
railway variables set LOG_LEVEL=INFO
railway variables set SQLITE_DB_PATH=./data/telemetry.db
railway variables set FAISS_INDEX_PATH=./data/faiss.index
railway variables set ADAPTIVE_THRESHOLD_ENABLED=true
railway variables set TEST_MODE=false

# 5. Deploy
railway up

# 6. Get your public URL
railway domain
# → contextforge-production.up.railway.app (or similar)

# 7. Verify
curl https://your-railway-url.up.railway.app/health
# → {"status":"ok","version":"1.0.0"}
```

### Railway Dashboard Configuration

After deploying, configure these settings in the Railway dashboard:

1. **Usage Alerts:**
   - Go to Project Settings → Usage
   - Set a spending limit of **$5/month** (free tier limit)
   - Enable email alerts at 80% usage ($4)

2. **Environment:**
   - Verify all environment variables are set in the Variables tab
   - `REDIS_URL` should reference the Railway Redis plugin: `${{Redis.REDIS_URL}}`

3. **Volumes (optional):**
   - Railway supports persistent volumes for the FAISS index and SQLite database
   - Add a volume mount at `/app/data` if you need data persistence across deploys

4. **Custom Domain (optional):**
   - Go to Settings → Domains
   - Add a custom domain or use the Railway-generated URL

### Railway Architecture

```
Railway Project
├── ContextForge Service (Dockerfile)
│   ├── Port: $PORT (auto-assigned by Railway)
│   ├── Health Check: GET /health
│   └── Volume: /app/data (FAISS + SQLite)
└── Redis Plugin (managed)
    └── Auto-provisioned, REDIS_URL injected
```

### Free Tier Limits

| Resource | Free Tier Limit | ContextForge Usage |
|----------|----------------|-------------------|
| Execution Hours | 500 hrs/month | ~720 hrs (always-on — may need Hobby plan) |
| Memory | 512 MB | ~300 MB (app + model) |
| Bandwidth | — | Minimal |
| Cost Credits | $5/month | Fits for low traffic |

> **Tip:** For always-on deployment, the Railway Hobby plan ($5/month) is recommended. The free trial provides $5 in credits which should last about a month for a low-traffic deployment.

---

## Docker on VPS (Alternative)

If you prefer to self-host on a VPS (DigitalOcean, AWS EC2, Linode, etc.):

### Quick Deploy

```bash
# On your VPS
git clone https://github.com/Ayush-o1/contextforge.git
cd contextforge

# Configure
cp .env.example .env
nano .env  # Add your OPENAI_API_KEY

# Deploy
docker compose up -d --build

# Verify
curl http://localhost:8000/health
```

### Nginx Reverse Proxy (HTTPS)

Create `/etc/nginx/sites-available/contextforge`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE streaming support
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding off;
    }
}
```

Then enable HTTPS with Certbot:

```bash
sudo ln -s /etc/nginx/sites-available/contextforge /etc/nginx/sites-enabled/
sudo certbot --nginx -d your-domain.com
sudo systemctl restart nginx
```

---

## Environment Variables Reference

See [CONFIGURATION.md](CONFIGURATION.md) for the complete list. The critical variables for deployment are:

| Variable | Required | Description |
|----------|:--------:|-------------|
| `OPENAI_API_KEY` | ✅ | Your OpenAI API key |
| `REDIS_URL` | ✅ | Redis connection string (Railway: `${{Redis.REDIS_URL}}`) |
| `SIMILARITY_THRESHOLD` | No | Cache similarity threshold (default: 0.92) |
| `LOG_LEVEL` | No | Logging level (default: INFO) |
| `TEST_MODE` | No | Force cheapest model (default: false) |

---

## Monitoring

### Health Check

```bash
curl https://your-url/health
# → {"status":"ok","version":"1.0.0"}
```

### Dashboard

Open `https://your-url/dashboard/` in a browser to see the real-time telemetry dashboard.

### Telemetry API

```bash
# Recent requests
curl https://your-url/v1/telemetry?limit=10

# Summary stats
curl https://your-url/v1/telemetry/summary
```

---

## Troubleshooting

### Railway: Build fails

- Check that `Dockerfile` is in the repository root
- Verify `railway.json` has correct `dockerfilePath`
- Check Railway build logs for dependency errors

### Railway: Redis connection refused

- Ensure the Redis plugin is provisioned: `railway add --plugin redis`
- Verify `REDIS_URL` is set to `${{Redis.REDIS_URL}}`

### Embedding model download timeout

The embedding model (80MB) is downloaded during Docker build. If the build times out:
- The Dockerfile pre-downloads the model in the builder stage
- If Railway times out, increase the build timeout in project settings

### Data persistence

- FAISS index and SQLite database are stored in `/app/data`
- On Railway, add a persistent volume mount at `/app/data`
- With Docker Compose, the `app-data` named volume persists across restarts
