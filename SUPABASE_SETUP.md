# Supabase Setup for Basafe Admin Dashboard

## 🚀 Complete Step-by-Step Guide

This guide will get your Supabase database running in ~10 minutes.

---

## Step 1: Create Supabase Account (2 minutes)

### 1.1 Go to Supabase
- Open: https://supabase.com
- Click **"Start your project"** or **"Sign Up"**

### 1.2 Sign Up
- **Email:** Use your email
- **Password:** Create strong password
- Click **"Sign Up"**
- Verify email (check inbox)

### 1.3 You're in!
You should now see the Supabase dashboard.

---

## Step 2: Create a New Project (3 minutes)

### 2.1 Create Project
1. Click **"New Project"** (or **"Create a new project"**)
2. Fill in:
   - **Name:** `basafe`
   - **Database Password:** Create strong password (save this!)
   - **Region:** Choose closest to you (US East, EU, etc.)
3. Click **"Create new project"**

### 2.2 Wait for Setup
- Supabase creates your database (takes ~1-2 minutes)
- You'll see a progress bar
- Wait for it to complete

**Tip:** Copy and save the database password somewhere safe!

---

## Step 3: Get Connection String (3 minutes)

### 3.1 Go to Settings
1. In Supabase dashboard, click **"Settings"** (gear icon, bottom left)
2. Click **"Database"** (left sidebar)

### 3.2 Find Connection String
1. Look for **"Connection string"** section
2. Select **"URI"** (not "Connection pooler")
3. **Copy the full string** (looks like):
   ```
   postgresql://postgres.xxxxx:password@db.xxxxx.supabase.co:5432/postgres
   ```

### 3.3 Save It
- Paste into a text editor
- Keep it safe (contains your password)
- You'll use this in Step 4

**⚠️ IMPORTANT:** 
- Make sure you copied the full string
- It should start with `postgresql://`
- Should include your password

---

## Step 4: Update Render Services (2 minutes each)

You need to add the database connection to BOTH your Render services.

### 4.1 Update PUBLIC APP (basafe)

1. Go to Render Dashboard: https://dashboard.render.com
2. Click **"basafe"** service (your public app)
3. Click **"Settings"** (left sidebar)
4. Scroll to **"Environment Variables"**
5. If `DATABASE_URL` exists:
   - Click to edit it
   - Replace with Supabase connection string
   - Click **"Save Changes"**
6. If `DATABASE_URL` doesn't exist:
   - Click **"Add Environment Variable"**
   - **Key:** `DATABASE_URL`
   - **Value:** [Paste Supabase connection string]
   - Click **"Add"**

7. **Render will automatically redeploy** (watch the logs)

**Verification:** In logs, should see:
```
Basafe X.X.X listening at http://0.0.0.0:PORT
```

### 4.2 Update ADMIN APP (basafe-admin)

**Repeat the same for your admin service:**

1. Go to Render Dashboard
2. Click **"basafe-admin"** service
3. Click **"Settings"**
4. Add/update `DATABASE_URL` with **SAME Supabase connection string**
5. Add these additional variables:

| Key | Value |
|-----|-------|
| `GEOSAFE_ADMIN_ENABLED` | `true` |
| `GEOSAFE_ADMIN_USERNAME` | `admin` |
| `GEOSAFE_ADMIN_PASSWORD` | Strong password here |
| `GEOSAFE_LOG_LEVEL` | `INFO` |
| `GEOSAFE_RUNTIME_DATA_MODE` | `snapshot` |

6. Click **"Save Changes"**
7. Wait for redeploy (watch logs)

---

## Step 5: Verify Both Services Deploy (3 minutes)

### 5.1 Check Public App
1. Go to **basafe** service logs
2. Wait for: `"listening at http://0.0.0.0:PORT"`
3. Visit: `https://basafe-xxxx.onrender.com/`
4. Should load normally ✅

**If it fails:**
- Check logs for database connection errors
- Verify `DATABASE_URL` is correct (no typos, full string)
- Redeploy: push a commit or click "Manual Deploy"

### 5.2 Check Admin App
1. Go to **basafe-admin** service logs
2. Wait for: `"listening at http://0.0.0.0:PORT"`
3. Visit: `https://basafe-admin-xxxx.onrender.com/admin/login`
4. Should see login form ✅

**If it fails:**
- Check logs for errors
- Verify all environment variables are set
- Verify ADMIN_USERNAME and PASSWORD are set
- Redeploy

---

## Step 6: Test the Integration (5 minutes)

### 6.1 Submit a Test Report

1. Open: `https://basafe-xxxx.onrender.com/report-damage`
2. Click on the map to place a pin
3. Fill out a test damage report (any values work)
4. Click **"Send report"**
5. You should see: "Report received - Thank you"

**Important:** Remember the location or details of your test report!

### 6.2 View Report in Admin

1. Open: `https://basafe-admin-xxxx.onrender.com/admin`
2. You'll see login page
3. Log in with:
   - **Username:** `admin` (or whatever you set)
   - **Password:** (what you configured)
4. Click **"Reports"** (left sidebar)
5. **You should see the report you just submitted!** ✅

If you see your report:
- ✅ Supabase connection works
- ✅ Reports are persisted
- ✅ Admin dashboard sees them

### 6.3 Test Report Triage

1. Click on your test report
2. Change status: **new** → **acknowledged**
3. Click **"Save"**
4. Go back to public app and refresh
5. Reports should sync ✅

---

## Step 7: Test Evacuation Center Publishing

### 7.1 Edit a Center

1. In admin dashboard, click **"Evacuation Centers"**
2. Click any center card
3. Edit the **Name** (add "TEST" to it)
4. Click **"Save"**
5. Click **"Publish"** (important!)
6. Wait for confirmation

### 7.2 Verify on Public App

1. Go to public app map: `https://basafe-xxxx.onrender.com/map`
2. Search for the center you edited
3. **The name should show your change** ✅

If it does:
- ✅ Admin edits work
- ✅ Evacuation centers publish correctly
- ✅ Database sync is working

---

## ✅ Final Verification Checklist

- [ ] Supabase account created
- [ ] Supabase project created
- [ ] Database password saved securely
- [ ] Connection string copied
- [ ] DATABASE_URL added to PUBLIC APP (basafe)
- [ ] DATABASE_URL added to ADMIN APP (basafe-admin)
- [ ] Admin environment variables configured (USERNAME, PASSWORD)
- [ ] PUBLIC APP redeployed and working
- [ ] ADMIN APP redeployed and working
- [ ] Can log into admin dashboard
- [ ] Can submit report on public app
- [ ] Report appears in admin dashboard
- [ ] Can triage report (change status)
- [ ] Can edit evacuation center
- [ ] Can publish center changes
- [ ] Changes appear on public app map

**All checked?** 🎉 You're done!

---

## 🔒 Secure Your Credentials

### Save These Safely:
1. **Supabase Database Password** → Password manager
2. **Supabase Connection String** → Password manager
3. **Admin Username/Password** → Password manager
4. **Render Environment Variables** → Already in Render (don't share URLs)

### Share with Team:
- **Admin URL:** `https://basafe-admin-xxxx.onrender.com/admin`
- **Admin Username:** (from GEOSAFE_ADMIN_USERNAME)
- **Admin Password:** (from GEOSAFE_ADMIN_PASSWORD)

**Never share:**
- Connection strings
- Passwords in chat/email
- Render dashboard URLs

---

## 🆘 Troubleshooting

### "Connection refused" or database error in logs

**Solution:**
1. Copy connection string again from Supabase
2. Make sure it's the "URI" version (not "Connection pooler")
3. Check for typos (especially password)
4. Paste into Render again
5. Redeploy

### "Can't log into admin"

**Solution:**
1. Double-check USERNAME and PASSWORD in Render settings
2. Make sure GEOSAFE_ADMIN_ENABLED=true is set
3. Try logging out and back in
4. Check admin app logs for auth errors
5. Redeploy admin service

### "Submit report but it doesn't appear in admin"

**Solution:**
1. Verify both apps use same DATABASE_URL
2. Check public app logs show report was submitted
3. Refresh admin page
4. Check admin app logs for database errors
5. Verify GEOSAFE_ADMIN_ENABLED=true on admin app

### Reports submitted but don't persist

**Solution:**
1. Verify DATABASE_URL is using Supabase (not Render Postgres)
2. Check connection string format: should be `postgresql://`
3. Verify no typos in connection string
4. Test Supabase connection directly from Supabase dashboard

---

## 📊 What You Now Have

✅ **Persistent Database** - Reports never lost  
✅ **Remote Admin Access** - Manage from anywhere  
✅ **Real-time Sync** - Changes appear instantly  
✅ **Audit Logs** - Who did what and when  
✅ **Free Tier** - $0/month (no 30-day expiration)  
✅ **Easy Scale** - Upgrade if needed  

---

## 🎯 Next Steps

1. Follow Steps 1-7 above
2. Verify integration works
3. Save credentials securely
4. Share access with team if needed
5. Monitor reports coming in!

**Ready?** Start with Step 1! 🚀
