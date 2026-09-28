# Admin Dashboard Deployment Checklist

## ✅ Pre-Deployment Checklist

- [ ] Have your Render account open (dashboard.render.com)
- [ ] Know your PostgreSQL connection string (from public app DATABASE_URL)
- [ ] Have a strong admin password ready
- [ ] Your GitHub repo is up to date

---

## 🗄️ Step 1: Create PostgreSQL Database (If Needed)

### Check if you have a database:
1. Go to your Render Dashboard
2. Look for **Storage** tab
3. If you see a **Postgres** instance:
   - ✅ You have a database - copy the `External Database URL`
   - This is your `DATABASE_URL`
   - If you don't have one, create it (see below)

### If you need to create Postgres:
1. Go to **Storage** → **Create** → **Postgres**
2. Configure:
   - **Name:** `basafe-db`
   - **Region:** (match your app region)
   - **Instance Type:** Free tier (sufficient)
3. Wait for creation (~2 minutes)
4. Copy the **External Database URL** (looks like `postgresql://user:pass@host:port/db`)
5. Keep this for Step 2 and 3

---

## 📱 Step 2: Create Admin Web Service

### On Render Dashboard:

1. Click **New** → **Web Service**
2. **Select Repository:**
   - Choose `Basafe-2.0.1` (or your repo name)
   - Click **Connect**
   
3. **Configure Service:**
   - **Name:** `basafe-admin`
   - **Environment:** `Python 3`
   - **Region:** (same as your other service)
   - **Build Command:** `pip install -e .`
   - **Start Command:** `python -m geosafe.server --host 0.0.0.0 --port $PORT`
   - **Plan:** Free (sufficient for MVP)

4. Click **Create Web Service**
5. Wait for build to start (watch the logs)

---

## 🔐 Step 3: Configure Admin Environment Variables

### While the admin service is building:

1. Go to `basafe-admin` service (your new service)
2. Click **Settings** (on the left)
3. Scroll to **Environment Variables**
4. Add these variables:

| Key | Value | Notes |
|-----|-------|-------|
| `DATABASE_URL` | `postgresql://user:pass@host:port/db` | Copy from your Postgres service or public app |
| `GEOSAFE_ADMIN_ENABLED` | `true` | Enables admin features |
| `GEOSAFE_ADMIN_USERNAME` | `admin` | Change to your preference |
| `GEOSAFE_ADMIN_PASSWORD` | `YourStrongPassword123!` | **Use a strong random password** |
| `GEOSAFE_LOG_LEVEL` | `INFO` | Logging level |
| `GEOSAFE_RUNTIME_DATA_MODE` | `snapshot` | Use bundled data |

5. Click **Save Changes**
6. Render will automatically redeploy with new variables

---

## 🌐 Step 4: Update Public App Environment

### Ensure public app uses same database:

1. Go to **basafe** service (your public app)
2. Click **Settings**
3. Scroll to **Environment Variables**
4. Check if `DATABASE_URL` exists:
   - ✅ If yes, verify it matches the admin's `DATABASE_URL`
   - ❌ If no, add it:

| Key | Value |
|-----|-------|
| `DATABASE_URL` | Same as Step 3 |

5. Click **Save Changes** if you made updates

---

## ✅ Step 5: Verify Deployments

### Check public app (basafe):
1. Wait for build to complete
2. Check logs - should see: `listening at http://0.0.0.0:PORT`
3. Visit: `https://basafe-xxxx.onrender.com/`
4. Should load normally ✅

### Check admin app (basafe-admin):
1. Wait for build to complete  
2. Check logs for errors
3. Visit: `https://basafe-admin-xxxx.onrender.com/admin/login`
4. Should see login form ✅

If either fails:
- Check the logs for error messages
- Verify DATABASE_URL is correct (no typos)
- Verify passwords/credentials are set
- Redeploy by pushing a commit or clicking "Manual Deploy"

---

## 🧪 Step 6: Test the Integration

### Test: Submit a damage report

1. Open: `https://basafe-xxxx.onrender.com/report-damage`
2. Fill out and submit a test report
3. Go back to admin: `https://basafe-admin-xxxx.onrender.com/admin`
4. Log in with your credentials
5. Go to **Reports** section
6. **You should see the report you just submitted** ✅

### Test: Change report status

1. In the Reports page, click a report
2. Change status: `new` → `acknowledged`
3. Go back to public app and check report is updated ✅

### Test: Edit evacuation center

1. In admin, go to **Evacuation Centers**
2. Click a center card
3. Edit the name (e.g., add "UPDATED" to the name)
4. Click **Save** then **Publish**
5. Go to public app `/map`, search for that center
6. **Name should show your change** ✅

### Test: Check audit logs

1. In admin dashboard **Overview**
2. Look for audit log entries showing:
   - Reports triaged
   - Centers published
   - Timestamp and actor recorded ✅

---

## 🔑 Step 7: Secure Your Credentials

### Store admin credentials safely:

1. **Do NOT** share the password in chat/email
2. **Do NOT** put it in version control
3. **Store in:**
   - Password manager (1Password, LastPass, Bitwarden)
   - Secure note app (Apple Notes, Notion)
   - Only share with authorized team members

### Credentials needed by team:
- **Admin URL:** `https://basafe-admin-xxxx.onrender.com/admin`
- **Username:** (from GEOSAFE_ADMIN_USERNAME)
- **Password:** (from GEOSAFE_ADMIN_PASSWORD)

---

## 📋 Final Verification Checklist

- [ ] PostgreSQL database created on Render
- [ ] Public app (basafe) environment updated with DATABASE_URL
- [ ] Admin service (basafe-admin) created
- [ ] Admin environment variables configured
- [ ] Both services deployed successfully (no build errors)
- [ ] Can access `/admin/login` from admin service
- [ ] Can log in with credentials
- [ ] Test report submission and retrieval works
- [ ] Can triage reports in admin
- [ ] Can edit and publish evacuation centers
- [ ] Audit logs showing changes
- [ ] Credentials stored securely

---

## 🎉 You're Done!

Once all checks pass, you have:
✅ Production-ready admin dashboard  
✅ Persistent citizen damage reports  
✅ Remote evacuation center management  
✅ Complete audit trail  
✅ Real-time report triage  

---

## Troubleshooting

### Admin service won't build
```
Error: "pip install -e . failed"
Solution: 
  1. Check that pyproject.toml exists in repo
  2. Check build logs for dependency errors
  3. Try redeploying (push a commit or Manual Deploy)
```

### Can't access admin login
```
Problem: 404 or connection refused
Solution:
  1. Check service is deployed (green status)
  2. Wait 2-3 minutes for first deploy
  3. Check that GEOSAFE_ADMIN_ENABLED=true is set
  4. Check logs for startup errors
```

### Reports don't appear in admin
```
Problem: Submit report but it's not in admin
Solution:
  1. Verify both apps use same DATABASE_URL
  2. Check if report was actually submitted (public app logs)
  3. Refresh admin page and try again
  4. Check admin logs for errors
```

### Can't log in
```
Problem: Username/password rejected
Solution:
  1. Double-check username and password exactly
  2. Check for extra spaces in credentials
  3. Verify GEOSAFE_ADMIN_USERNAME and PASSWORD are set
  4. Try logging out and back in
  5. Redeploy admin service to ensure vars take effect
```

---

**Questions?** Check `ADMIN_DEPLOYMENT_PLAN.md` for detailed info on each step.
