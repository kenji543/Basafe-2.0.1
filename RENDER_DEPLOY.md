# Render Deployment Checklist

## Before You Start
- [ ] GitHub account connected to your repository
- [ ] Render.com account created

## Step 1: Push Latest Code to GitHub
```bash
git add -A
git commit -m "Prepare for Render deployment: add render.yaml and deployment docs"
git push origin main
```

## Step 2: Create Render Web Service

1. Go to https://dashboard.render.com
2. Click **New** → **Web Service**
3. Select your GitHub repository
4. Fill in these values:
   - **Name:** `basafe`
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -e .`
   - **Start Command:** `python -m geosafe.server --host 0.0.0.0 --port $PORT`
   - **Plan:** Free (sufficient for MVP)

5. Click **Create Web Service**
6. Wait for deployment to complete (watch the logs)

## Step 3: Verify Deployment

Once "Service is live" appears:

```bash
# Test the app
curl https://basafe-xxxxx.onrender.com/

# Test reports endpoint (should return 405, not 503)
curl https://basafe-xxxxx.onrender.com/api/v1/reports
```

## Step 4: Test Damage Reports

1. Open https://basafe-xxxxx.onrender.com/report-damage
2. Fill out and submit a test report
3. Reports now persist permanently on Render

## That's It!

Your app is live with:
- ✅ Persistent SQLite storage
- ✅ Working damage reports
- ✅ Auto-deploys on GitHub pushes
- ✅ Free tier pricing

## Troubleshooting

**App won't start?**
- Check the build log in Render dashboard for errors
- Ensure `pyproject.toml` exists
- Verify Python 3.12 is available

**Reports still say "unavailable"?**
- Redeploy by pushing a change to GitHub
- Or manually redeploy in Render dashboard

**Need to see the database?**
- Render's file browser shows `/opt/render/project/src/data/geosafe.db`
- Download for local backup

## Next Steps

- Add a custom domain (Render → Settings → Custom Domain)
- Enable GitHub auto-deploys if not already active
- Set up periodic backups (see [render-deployment.md](docs/render-deployment.md))

See [docs/render-deployment.md](docs/render-deployment.md) for detailed documentation.
