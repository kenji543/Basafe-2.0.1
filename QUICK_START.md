# 🚀 Quick Start: Admin Dashboard with Supabase

**Time needed: ~15 minutes**

---

## What You'll Have After This

✅ Citizen damage reports **persist forever** (no 30-day expiration)  
✅ Admin dashboard **deployed to production**  
✅ Real-time **report triage** and **evacuation center editing**  
✅ Complete **audit logs** of all changes  
✅ **FREE** for first 500MB of data  

---

## 5 Easy Steps

### 1️⃣ Create Supabase Database (2 min)
```
1. Go to supabase.com
2. Sign up (free)
3. Click "New Project"
4. Name: "basafe"
5. Save your database password!
```

### 2️⃣ Get Connection String (1 min)
```
1. In Supabase, go Settings → Database
2. Copy the "URI" string (postgresql://...)
3. Save it somewhere safe
```

### 3️⃣ Add to Public App on Render (2 min)
```
1. Go to Render Dashboard
2. Click "basafe" service
3. Settings → Environment Variables
4. Add/update DATABASE_URL = [paste Supabase string]
5. Save (auto redeploy)
```

### 4️⃣ Add to Admin App on Render (2 min)
```
1. Create new service or use existing basafe-admin
2. Add these environment variables:

   DATABASE_URL = [same Supabase string]
   GEOSAFE_ADMIN_ENABLED = true
   GEOSAFE_ADMIN_USERNAME = admin
   GEOSAFE_ADMIN_PASSWORD = [strong password]
   GEOSAFE_LOG_LEVEL = INFO
   GEOSAFE_RUNTIME_DATA_MODE = snapshot

3. Save (auto redeploy)
```

### 5️⃣ Test It Works (5 min)
```
1. Submit a test report:
   https://basafe-xxxx.onrender.com/report-damage

2. View in admin:
   https://basafe-admin-xxxx.onrender.com/admin
   
3. Log in with username/password you set

4. Go to "Reports" → should see your test report ✅

5. Change report status: new → acknowledged → resolved

6. Test evacuation center edit:
   - Edit a center name
   - Click "Publish"
   - Check public app map - should show change ✅
```

---

## 📋 Complete Checklists

### ✅ Supabase Setup
- [ ] Supabase account created
- [ ] Project created
- [ ] Database password saved
- [ ] Connection string copied

### ✅ Render Configuration
- [ ] Public app: DATABASE_URL added
- [ ] Public app: redeployed
- [ ] Admin app: all environment variables added
- [ ] Admin app: redeployed

### ✅ Testing
- [ ] Can access `https://basafe-xxxx.onrender.com/`
- [ ] Can access `https://basafe-admin-xxxx.onrender.com/admin/login`
- [ ] Can log into admin dashboard
- [ ] Can submit damage report
- [ ] Report appears in admin dashboard
- [ ] Can triage report
- [ ] Can edit evacuation center
- [ ] Can publish evacuation center
- [ ] Changes appear on public app

---

## 🔑 Keep These Safe

**Store in password manager:**
- Supabase database password
- Supabase connection string
- Admin username
- Admin password

**Render keeps these, no need to save:**
- Environment variables (in Render dashboard)

---

## 🆘 If Something Breaks

| Problem | Fix |
|---------|-----|
| **Connection refused** | Verify DATABASE_URL matches Supabase URI |
| **Can't log into admin** | Check ADMIN_USERNAME and PASSWORD are set |
| **Reports don't appear** | Both apps must use same DATABASE_URL |
| **Services won't deploy** | Check logs for database/env var errors |

---

## 📖 Full Guides (If Needed)

- **SUPABASE_SETUP.md** - Detailed step-by-step walkthrough
- **ADMIN_DEPLOYMENT_PLAN.md** - All deployment options
- **ADMIN_DEPLOY_CHECKLIST.md** - Interactive checklist
- **DATABASE_OPTIONS.md** - Why Supabase vs alternatives

---

## 🎉 After You're Done

You now have:

| Feature | Status |
|---------|--------|
| Citizen reports | ✅ Persistent (forever) |
| Admin dashboard | ✅ Deployed & accessible |
| Report triage | ✅ Working |
| Evacuation editing | ✅ Real-time sync |
| Audit logs | ✅ Complete history |
| Cost | ✅ $0/month (free tier) |

---

## Next

Follow **SUPABASE_SETUP.md** for detailed step-by-step instructions.

Any questions? Check the **🆘 Troubleshooting** section above or read the full guides.

**Ready?** Open SUPABASE_SETUP.md and start! 🚀
