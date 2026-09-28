# Persistent Database Options for Basafe Admin Dashboard

## The Problem
Render's free PostgreSQL **expires after 30 days** and is deleted. This won't work for production.

We need a **persistent, affordable database** for:
- Citizen damage reports
- Evacuation center edits
- Audit logs
- Analytics

---

## ✅ Recommended Options (By Cost & Ease)

### Option 1: **Supabase** (FREE + PAID) ⭐ RECOMMENDED
**Best for:** Quick setup, built-in auth, generous free tier

**Free Tier:**
- Up to 500MB database
- Perfect for MVP/early stage
- No automatic deletion
- Built-in PostgreSQL

**Cost After Free:**
- $15/month for 1GB
- Scales up as needed

**Setup Time:** 5 minutes

**Pros:**
- ✅ Free tier is actually persistent (no 30-day limit)
- ✅ PostgreSQL compatible (works with our code)
- ✅ Built-in authentication
- ✅ Automatic backups
- ✅ Real-time API
- ✅ Great for small projects

**Cons:**
- Requires separate account
- Free tier has data limits

**Steps:**
1. Go to supabase.com
2. Sign up (free)
3. Create new project
4. Copy "postgresql://" connection string
5. Add to Render as DATABASE_URL

---

### Option 2: **Railway** (PAID) 💰
**Best for:** Simple, affordable, includes deployment

**Cost:**
- $5/month PostgreSQL database
- Auto-scaling based on usage
- No expiration
- Includes 5GB storage on free plan ($0)

**Setup Time:** 5 minutes

**Pros:**
- ✅ Can deploy entire app to Railway (not just DB)
- ✅ Simple pricing
- ✅ No hidden fees
- ✅ Great documentation

**Cons:**
- Minimum $5/month cost
- Requires billing

**Steps:**
1. Go to railway.app
2. Connect GitHub
3. Create PostgreSQL service
4. Copy connection string
5. Add to Render

---

### Option 3: **AWS RDS PostgreSQL** (PAID) 💸
**Best for:** Enterprise, scalability, advanced features

**Cost:**
- $0.013/hour = ~$10/month (t3.micro)
- Scales up for growth
- Automatic backups

**Setup Time:** 15 minutes

**Pros:**
- ✅ Enterprise grade
- ✅ Highly available
- ✅ Automated backups
- ✅ Monitoring & alarms

**Cons:**
- More complex to set up
- Slightly higher cost at scale
- AWS account required

---

### Option 4: **Keep SQLite Locally** (FREE) ⚠️
**Best for:** MVP with manual report export

**How it works:**
1. Keep admin dashboard LOCAL only
2. Users submit reports on public app (lost on restart)
3. Admin periodically exports reports to CSV
4. Manual backup process

**Cost:** $0

**Pros:**
- ✅ No database cost
- ✅ Simple infrastructure

**Cons:**
- ❌ Reports still lost on Render restarts
- ❌ No real-time admin access
- ❌ Manual exports needed
- ❌ Not production ready

---

## 📊 Comparison Table

| Feature | Supabase | Railway | AWS RDS | SQLite Local |
|---------|----------|---------|---------|--------------|
| **Free Tier** | 500MB, persistent | 5GB | 12 months $300 credit | N/A |
| **After Free** | $15/mo | $5/mo | ~$10/mo | N/A |
| **Setup Time** | 5 min | 5 min | 15 min | 0 min |
| **Expiration** | Never ✅ | Never ✅ | Never ✅ | N/A |
| **PostgreSQL** | ✅ Yes | ✅ Yes | ✅ Yes | ❌ SQLite |
| **Admin Access** | ✅ Remote | ✅ Remote | ✅ Remote | ❌ Local only |
| **Auto Backup** | ✅ Yes | ✅ Yes | ✅ Yes | ❌ Manual |
| **Reports Persist** | ✅ Yes | ✅ Yes | ✅ Yes | ❌ Lost on restart |

---

## 🎯 My Recommendation

### For MVP (Fast & Free):
**Use Supabase** - It has a genuine free tier with no 30-day expiration, and it's PostgreSQL compatible.

### For Early Stage (After MVP):
**Use Railway** - Simple $5/month, can deploy entire app there if needed

### For Long-term Production:
**Use AWS RDS or managed service** - Better control, monitoring, backups

---

## 🚀 Quick Setup: Supabase (Recommended)

### 1. Create Supabase Account
```
1. Go to supabase.com
2. Click "Start Your Project"
3. Sign up (free)
```

### 2. Create a New Project
```
1. Click "New Project"
2. Enter name: "basafe"
3. Create strong password
4. Region: (pick closest to your users)
5. Click "Create New Project"
```

### 3. Get Connection String
```
1. In Supabase dashboard, go to Settings
2. Click "Database"
3. Copy "URI" (starts with postgresql://)
4. Keep it safe
```

### 4. Add to Render
```
For PUBLIC APP (basafe):
  Go to Settings → Environment Variables
  Add: DATABASE_URL = [your Supabase connection string]
  Save

For ADMIN APP (basafe-admin):
  Go to Settings → Environment Variables
  Add: DATABASE_URL = [same Supabase connection string]
  Save
```

### 5. Redeploy Both Services
```
1. Push a commit (or Manual Deploy)
2. Wait for both services to rebuild
3. Test: Submit report on public app → see it in admin
```

**That's it!** You now have persistent reports. 🎉

---

## Cost Comparison (Annual)

| Option | Year 1 | Year 2+ | Notes |
|--------|--------|---------|-------|
| **Supabase Free** | $0 | $0 | 500MB limit, fine for MVP |
| **Supabase Paid** | $0 (free tier) | $180/year | If you exceed 500MB |
| **Railway** | $0 (free tier) | $60/year | $5/month, simple |
| **AWS RDS** | $120 credit | $120/year | $10/month |
| **SQLite (Render)** | $0 | $0 | ❌ Reports lost |

---

## What to Do RIGHT NOW

### Choose one:

**Option A: Use Supabase (Recommended)**
- Most painless free option
- No 30-day expiration
- Works perfectly with our PostgreSQL setup
- Free tier suitable for MVP

**Option B: Use Railway**
- Simple $5/month
- More generous free tier (5GB)
- Can host entire app there later

**Option C: Keep current setup**
- Accept that reports are lost on Render
- Keep admin dashboard local-only
- Export reports manually when needed

---

## Next Steps

### If you choose Supabase:
1. Sign up at supabase.com
2. Create project
3. Copy connection string
4. Follow "Quick Setup: Supabase" section above
5. Test with a sample report

### If you choose Railway:
1. Sign up at railway.app
2. Connect GitHub
3. Create PostgreSQL service
4. Copy connection string
5. Add to Render environment variables

### If you keep local-only:
1. Document that reports aren't persistent on production
2. Export reports manually via admin dashboard
3. Focus on other features

---

## Important Notes

⚠️ **Do NOT use Render's free PostgreSQL for production** - it will be deleted after 30 days

✅ **Use Supabase, Railway, or AWS** - they're persistent and affordable

✅ **Same DATABASE_URL for both apps** - public app and admin need to access same database

✅ **Test end-to-end** - submit report on public app, verify it appears in admin

---

**Recommendation: Go with Supabase for simplicity, or Railway if you want slightly more storage. Both work great with our setup!**
