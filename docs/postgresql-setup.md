# PostgreSQL Setup for Basafe

This guide explains how to set up PostgreSQL for Basafe, enabling persistent storage for damage reports on serverless platforms like Vercel.

## Overview

Basafe now supports both SQLite (for local development) and PostgreSQL (for production). The application automatically detects which database to use based on the `DATABASE_URL` environment variable:

- **No `DATABASE_URL`** → Uses SQLite (local development)
- **`DATABASE_URL` set** → Uses PostgreSQL (production)

## Local Development (SQLite)

SQLite requires no configuration and is used by default:

```bash
# Install dependencies
python -m pip install -e .

# Run the public app
python -m geosafe.server

# Run the admin dashboard (separate database)
.\scripts\run_admin_dev.ps1
```

No changes needed for local development.

## Production Setup (PostgreSQL on Vercel)

### Step 1: Create a PostgreSQL Database

You have several options:

#### Option A: Vercel Postgres (Recommended for Vercel)
1. Go to your Vercel project dashboard
2. Go to **Storage** tab
3. Create a **Postgres** database
4. Copy the connection string (starts with `postgresql://`)

#### Option B: External Provider (AWS RDS, Supabase, Railway, etc.)
1. Create a PostgreSQL database
2. Get the connection string in format: `postgresql://user:password@host:port/dbname`

### Step 2: Set Environment Variables on Vercel

Add the database connection string to your Vercel project:

1. Go to **Settings** → **Environment Variables**
2. Add new variable:
   - **Name:** `DATABASE_URL`
   - **Value:** Your PostgreSQL connection string (from Step 1)
   - **Environments:** Select `Production` (and optionally `Preview`)
3. Save and redeploy

### Step 3: Initialize the Database Schema

The schema is automatically initialized on first request. However, you can manually initialize it:

```bash
# Export the DATABASE_URL
export DATABASE_URL="postgresql://user:password@host:port/dbname"

# Initialize the schema
python -c "
from geosafe.server import create_application
from pathlib import Path
api, repo, model = create_application()
"
```

### Step 4: Deploy

```bash
# Commit the changes
git add .
git commit -m "Add PostgreSQL support for persistent damage reports"

# Deploy to Vercel
vercel --prod
```

## Verifying the Setup

### Check Report Endpoint Health

```bash
# Should return 200 with JSON (reports available)
curl https://your-domain.vercel.app/api/v1/reports \
  -H "Accept: application/json"
```

**With PostgreSQL configured:**
```json
{
  "error": {
    "code": "method_not_allowed",
    "message": "Use POST to send a damage report."
  }
}
```
Status: 405 ✓

**Without PostgreSQL (ephemeral storage):**
```json
{
  "error": {
    "code": "report_intake_unavailable",
    "message": "Damage reports can't be received on this deployment yet..."
  }
}
```
Status: 503 ✗

### Test Report Submission

Use the web form at `https://your-domain.vercel.app/report-damage` or submit via API:

```bash
curl -X POST https://your-domain.vercel.app/api/v1/reports \
  -H "Content-Type: multipart/form-data" \
  -F "latitude=11.282" \
  -F "longitude=125.069" \
  -F "damage_type=flooding" \
  -F "severity=moderate" \
  -F "affected_count=5" \
  -F "name=Test Reporter" \
  -F "phone=09123456789"
```

## Connection Pooling

The application uses `psycopg2` connection pooling optimized for serverless environments:

- **Min connections:** 1
- **Max connections:** 5
- **Connection timeout:** 5 seconds
- **Statement timeout:** 30 seconds

These defaults are appropriate for Vercel's multi-worker model. Adjust in `geosafe/db.py` if needed.

## Troubleshooting

### "psycopg2 is required for PostgreSQL support"

Install psycopg2:
```bash
pip install psycopg2-binary
```

### Connection Refused

1. Verify `DATABASE_URL` is set correctly
2. Check if the database server is running
3. Verify firewall/security group allows connections from Vercel's IPs

### "too many connections"

PostgreSQL connection limit exceeded. Increase the pool size in `geosafe/db.py`:

```python
min_conns = 2
max_conns = 10  # Adjust as needed
```

### Reports Still Not Working

1. Check Vercel logs: `vercel logs`
2. Verify environment variable is set: `vercel env list`
3. Redeploy after adding the variable: `vercel --prod`

## Database Backups

### Using Vercel Postgres

Vercel automatically backs up your database. Access backups through:
1. Vercel Dashboard → Storage → Postgres → Backups

### Using External Provider

Follow your provider's backup procedures (e.g., AWS RDS automated backups, Supabase's built-in backups).

## Migration from SQLite to PostgreSQL

When migrating from SQLite to PostgreSQL:

1. Export data from SQLite if needed
2. Set up PostgreSQL database (Steps 1-2 above)
3. Initialize schema (Step 3)
4. Import historical data if required
5. Deploy with new `DATABASE_URL`

The application does NOT automatically migrate data—it initializes a fresh schema. Import data before switching if needed.

## Performance Notes

- **Connection pooling:** 5 connections should handle Vercel's typical load
- **Statement timeout:** 30 seconds prevents long-running queries
- **Indexes:** Schema includes indexes on frequently queried columns
- **WAL mode:** Not applicable to PostgreSQL (uses different durability mechanism)

## Cost Considerations

### Vercel Postgres
- Free tier: Limited storage, included with Vercel Pro
- Pricing details: https://vercel.com/docs/storage/vercel-postgres

### External Providers
- AWS RDS: $0.015-$0.15 per hour depending on instance size
- Supabase: Free tier includes 500MB
- Railway: $5-50 depending on usage

## Further Reading

- [Vercel Postgres Documentation](https://vercel.com/docs/storage/vercel-postgres)
- [psycopg2 Documentation](https://www.psycopg.org/psycopg2/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)

## Security Best Practices

1. **Never commit connection strings** to version control
2. **Use Vercel secrets management** for environment variables
3. **Restrict database access** to Vercel's IP ranges if possible
4. **Enable SSL** for database connections (usually default)
5. **Rotate credentials** regularly
6. **Monitor access logs** for unusual activity

---

Need help? Check the [main CLAUDE.md](../CLAUDE.md) for development instructions.
