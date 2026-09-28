# Deploying Basafe to Render

Render is a simple alternative to Vercel that provides persistent ephemeral storage by default, making SQLite deployments work seamlessly.

## Why Render?

- ✅ Persistent storage between deployments (SQLite works out of the box)
- ✅ Damage reports are automatically saved and persist
- ✅ No external database setup needed
- ✅ Free tier available
- ✅ Auto-deploys from GitHub
- ✅ Simple to set up

## Prerequisites

- GitHub repository with this code
- Render.com account (free)

## Step 1: Create Render Account

1. Go to https://render.com
2. Sign up with GitHub (recommended for auto-deployment)
3. Authorize Render to access your GitHub account

## Step 2: Create a Web Service

1. On Render dashboard, click **New +** → **Web Service**
2. Select your repository (`Basafe001-main`)
3. Fill in the details:
   - **Name:** `basafe` (or any name you prefer)
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -e .`
   - **Start Command:** `python -m geosafe.server --host 0.0.0.0 --port $PORT`
   - **Plan:** Free (or Starter if you want better performance)

## Step 3: Set Environment Variables

In the Web Service settings, add these environment variables:

| Key | Value | Purpose |
|-----|-------|---------|
| `GEOSAFE_RUNTIME_DATA_MODE` | `snapshot` | Use bundled data snapshot |
| `GEOSAFE_LOG_LEVEL` | `INFO` | Logging level |
| `GEOSAFE_ADMIN_ENABLED` | `false` | Disable admin on public deployment |

**Do NOT set `DATABASE_URL`** — SQLite will be used automatically.

## Step 4: Deploy

1. Click **Create Web Service**
2. Render starts deploying (watch the logs)
3. Wait for "Service is live" message
4. Your app is available at `https://basafe-xxxxx.onrender.com`

Subsequent pushes to your GitHub repo will auto-deploy.

## Step 5: Verify Reports Work

```bash
# Check report endpoint
curl https://basafe-xxxxx.onrender.com/api/v1/reports \
  -H "Accept: application/json"
```

Should return **405 Method Not Allowed** (not 503):
```json
{
  "error": {
    "code": "method_not_allowed",
    "message": "Use POST to send a damage report."
  }
}
```

## Step 6: Test the App

1. Visit your Render URL
2. Go to `/report-damage`
3. Fill out and submit a damage report
4. Report is saved to SQLite database on Render's persistent storage

## How Persistent Storage Works on Render

- Render provides **ephemeral persistent storage** at `/data`
- Files survive deployments and restarts
- Render's free tier includes up to 100GB
- Deleted when you delete the service

Your SQLite database (`data/geosafe.db`) automatically persists between deployments.

## Deploying Updates

Push to your GitHub repository:

```bash
git add .
git commit -m "Your changes"
git push origin main
```

Render automatically redeploys. Watch the logs to confirm.

## Important Notes

### Database Migrations

The database schema is initialized automatically on first run. If you update `db/schema.sql`, the changes apply to new instances.

**For existing instances:** You may need to manually migrate. Render keeps the database, so schema changes won't auto-apply.

### Admin Dashboard

The admin dashboard (`/admin`) is disabled on the public deployment (see `GEOSAFE_ADMIN_ENABLED=false`). This is intentional—the public app doesn't need an admin interface.

To run the admin locally:
```bash
.\scripts\run_admin_dev.ps1
```

### Monitoring

Access logs from Render dashboard:
1. Select your Web Service
2. Click **Logs** tab
3. View real-time application logs

## Troubleshooting

### "Service is starting" indefinitely

Check the build logs for errors:
1. Go to Service → **Events** tab
2. Look for build errors
3. Common issues:
   - Missing `pyproject.toml`
   - Python version mismatch
   - Dependencies not installing

### Reports still return 503

1. Redeploy the service (`git push` or manually trigger)
2. Check environment variable `GEOSAFE_ADMIN_ENABLED=false`
3. Check service logs for errors

### App runs but pages are blank

1. Check if `data/geosafe.snapshot.db` is bundled (should be in the repo)
2. Verify the build includes the data directory

### Out of memory errors

Render free tier has 0.5GB RAM. Basafe typically uses ~100-200MB at rest. If you hit limits:
- Upgrade to **Starter** plan
- Check logs for memory leaks
- Reduce the size of hazard datasets

## Costs

- **Free tier:** $0/month (sufficient for MVP)
- **Starter:** $7/month (recommended for production)
- **Standard:** $12+/month

The free tier provides:
- 750 hours/month (covers 24/7 uptime)
- 0.5GB RAM
- Automatic sleep after 15 minutes of inactivity (you can upgrade to prevent this)

## Backing Up Data

Render doesn't provide automated backups for ephemeral storage. To back up your SQLite database:

```bash
# Download database from Render (via SSH or export)
# Or use Render's file browser in the dashboard
```

For production, consider adding periodic backups:
1. Enable Render's persistent disk (paid feature)
2. Or switch to PostgreSQL with automated backups
3. Or set up a cron job to export reports

## Next Steps

### If you want to enable PostgreSQL later:

Render provides managed PostgreSQL. To switch:

1. Create a Render PostgreSQL database
2. Get the connection string
3. Add `DATABASE_URL` environment variable with the connection string
4. Redeploy

The application already supports PostgreSQL via the `geosafe/db.py` abstraction.

### If you want a custom domain:

1. Go to Web Service → **Settings**
2. Add **Custom Domain**
3. Point your DNS to the provided Render URL

## Further Reading

- [Render Documentation](https://render.com/docs)
- [Python on Render](https://render.com/docs/deploy-python)
- [Render Web Services](https://render.com/docs/web-services)

---

**Need help?** Check the [main CLAUDE.md](../CLAUDE.md) for development instructions or [postgresql-setup.md](postgresql-setup.md) for database details.
