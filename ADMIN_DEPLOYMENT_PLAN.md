# Deploy Admin Dashboard to Render

## Overview
Deploy the admin dashboard as a separate Render Web Service using the same PostgreSQL database as the public app. This allows admins to:
- View and triage citizen damage reports in real-time
- Edit and publish evacuation center changes
- Monitor visitor analytics
- Access complete audit logs

## Prerequisites
- Render account (already have one from public app deployment)
- PostgreSQL database on Render (shared with public app)
- Admin credentials configured

## Step 1: Set Up PostgreSQL (If Not Already Done)

### Check if DATABASE_URL is set on Render:
1. Go to Render Dashboard → basafe service → Settings
2. Check **Environment Variables** for `DATABASE_URL`
3. If it exists and points to Render Postgres, skip to Step 2
4. If not, create Postgres database:
   - Go to **Storage** tab
   - Click **Create** → **Postgres**
   - Copy connection string
   - Add to BOTH services' environment variables

## Step 2: Create Admin Web Service

### On Render Dashboard:

1. Click **New** → **Web Service**
2. Connect your GitHub repository (same as public app)
3. Fill in:
   - **Name:** `basafe-admin`
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -e .`
   - **Start Command:** `python -m geosafe.server --host 0.0.0.0 --port $PORT --admin-enabled`
   - **Plan:** Free (or Starter if you prefer)

### Add Environment Variables for Admin:

| Key | Value | Purpose |
|-----|-------|---------|
| `DATABASE_URL` | Same as public app | Shared database |
| `GEOSAFE_ADMIN_ENABLED` | `true` | Enable admin features |
| `GEOSAFE_ADMIN_USERNAME` | Your choice | Admin login |
| `GEOSAFE_ADMIN_PASSWORD` | Strong password | Admin login |
| `GEOSAFE_LOG_LEVEL` | `INFO` | Logging |
| `GEOSAFE_RUNTIME_DATA_MODE` | `snapshot` | Use bundled data |

**IMPORTANT:** Use a strong random password for `GEOSAFE_ADMIN_PASSWORD`

### Click "Create Web Service"

Wait for deployment to complete (watch the logs).

## Step 3: Update Public App Environment

The public app (`basafe` service) should also connect to the same database:

1. Go to basafe service → Settings → Environment Variables
2. Ensure `DATABASE_URL` is set to your Render Postgres
3. If missing, add it with the same value as admin service

## Step 4: Verify Both Services Use Same Database

### For public app (basafe):
1. Logs should show: `listening at http://0.0.0.0:PORT`
2. Should NOT show "reports blocked" messages

### For admin app (basafe-admin):
1. Logs should show service is live
2. Test: `curl https://basafe-admin-xxxx.onrender.com/admin/login`
3. Should return login page HTML (status 200)

## Step 5: Access Admin Dashboard

Once deployed:
1. Go to: `https://basafe-admin-xxxxx.onrender.com/admin`
2. You'll be redirected to `/admin/login`
3. Enter credentials:
   - Username: value of `GEOSAFE_ADMIN_USERNAME`
   - Password: value of `GEOSAFE_ADMIN_PASSWORD`
4. You should see the admin dashboard

## Step 6: Test End-to-End

### Test citizen reports flow:

1. Open public app: `https://basafe-xxxx.onrender.com/report-damage`
2. Submit a test damage report
3. Go to admin dashboard: `https://basafe-admin-xxxx.onrender.com/admin/reports`
4. **You should see the report you just submitted** ✅
5. Change its status: new → acknowledged → resolved
6. Verify audit log records the change

### Test evacuation center edits:

1. In admin dashboard, go to **Evacuation Centers**
2. Edit a center's name or coordinates
3. Click **Save** then **Publish**
4. Go to public app `/map` and search for that center
5. **Changes should appear immediately** ✅

### Check audit logs:

1. In admin dashboard, go to **Overview** or query admin tables
2. You should see entries for:
   - Reports triaged
   - Centers published
   - Any changes made

## Step 7: Secure for Production

### After testing, upgrade security:

**Optional but recommended:**

1. Add a WAF/rate limiting
2. Set up HTTPS (Render does this automatically)
3. Change password regularly
4. Monitor admin_audit_log for suspicious activity
5. Consider IP whitelisting (Render doesn't support this free-tier, but you could add basic auth)

## Environment Variable Reference

### Public App (basafe)
```
DATABASE_URL=postgresql://user:pass@host/db
GEOSAFE_RUNTIME_DATA_MODE=snapshot
GEOSAFE_LOG_LEVEL=INFO
```

### Admin App (basafe-admin)
```
DATABASE_URL=postgresql://user:pass@host/db (same as public app)
GEOSAFE_ADMIN_ENABLED=true
GEOSAFE_ADMIN_USERNAME=admin_username
GEOSAFE_ADMIN_PASSWORD=strong_random_password_here
GEOSAFE_LOG_LEVEL=INFO
GEOSAFE_RUNTIME_DATA_MODE=snapshot
```

## What This Achieves

✅ **Citizen Reports**
- Users submit reports on public app
- Stored in persistent Postgres database (not ephemeral)
- Admins can see and manage them in real-time

✅ **Evacuation Center Management**
- Admins edit centers in admin dashboard
- Click "Publish" to sync to public app
- Changes appear immediately on map
- All edits are audit-logged

✅ **Audit Trail**
- Every action logged with timestamp and actor
- Full history of who changed what and when
- Critical for compliance and accountability

✅ **Analytics**
- Visitor tracking and 7-day trends
- Reports received and triaged
- System health monitoring

## Troubleshooting

### Admin service won't start
- Check build logs for Python/dependency errors
- Verify DATABASE_URL is set
- Verify GEOSAFE_ADMIN_USERNAME and PASSWORD are set

### Can't access `/admin/login`
- Wait 2-3 minutes for Render to fully deploy
- Check service logs for errors
- Verify the URL is correct (basafe-admin-xxxx.onrender.com, not basafe)

### Reports don't appear in admin
- Check if report was actually submitted (check public app logs)
- Verify both services use same DATABASE_URL
- Redeploy both services if DATABASE_URL changed

### Evacuation center edits don't sync
- Make sure you clicked "Publish" (not just "Save")
- Check admin audit log to confirm publish action
- Refresh public app map
- Check if coordinates are valid (inside Basey)

## Next Steps

1. Create PostgreSQL database on Render (if needed)
2. Deploy admin service
3. Add environment variables
4. Test the flow
5. Secure credentials in a password manager
6. Document admin access for your team

---

**Once complete:**
- ✅ Reports submitted on production are persistent
- ✅ Admins can manage reports from anywhere
- ✅ Evacuation centers can be updated without redeploying
- ✅ Full audit trail of all changes
- ✅ Production-ready admin dashboard
