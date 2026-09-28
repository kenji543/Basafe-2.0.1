# Admin Dashboard Functionality Status

## Current State

### ✅ **What's Working (Locally)**

When running locally with both the public app (port 8000) and admin (port 8001):

1. **Evacuation Center Edits**
   - ✅ Admin can edit centers in `admin-dev.db` (draft)
   - ✅ Admin can **Publish** to `data/geosafe.db` (public app reads this)
   - ✅ Changes appear on http://127.0.0.1:8000/map within seconds
   - ✅ Audit logs record who/when changes were published
   - ✅ Photo uploads for centers work

2. **Citizen Damage Reports**
   - ✅ Public app (port 8000) receives reports → writes to `data/geosafe.db`
   - ✅ Admin dashboard reads reports from `data/geosafe.db`
   - ✅ Admin can triage reports (new → acknowledged → resolved)
   - ✅ Changes sync back to public app via audit log
   - ✅ Photo attachments are stored and retrievable

3. **Audit Logging**
   - ✅ All admin actions logged in `admin_audit_log` table
   - ✅ Records: actor, timestamp, action, entity type, details
   - ✅ Examples: publish_center, update_center, set_report_status

### ❌ **What's NOT Working (On Render Deployment)**

The admin dashboard is **dev-only and not deployed**. When users submit reports on Render:

1. **Evacuation Center Edits**
   - ❌ No admin dashboard access on production
   - ❌ Admins can't edit/publish center changes remotely
   - Workaround: Manually edit and redeploy

2. **Citizen Damage Reports**
   - ❌ Reports submitted on Render go to ephemeral `/tmp` database
   - ❌ Database is **deleted on every cold restart** (Render's free tier)
   - ❌ No admin interface to see/manage reports
   - ❌ Reports are **permanently lost**
   - ❌ No audit trail of received reports

3. **Audit Logging**
   - ❌ Audit logs only exist in local `admin-dev.db`
   - ❌ No production audit trail
   - ❌ No visibility into who accessed what

---

## The Core Problem

### Architecture Mismatch

```
LOCAL DEVELOPMENT (works perfectly)
├── Public app (port 8000)
│   └── reads/writes: data/geosafe.db
├── Admin app (port 8001)
│   ├── reads/writes: admin-dev.db (draft)
│   └── publishes to: data/geosafe.db
└── Sync: automatic & audited ✅

RENDER DEPLOYMENT (broken)
├── Public app (Render)
│   └── reads/writes: /tmp/geosafe.db (ephemeral!)
│       └── deleted on cold restart ❌
└── Admin app: doesn't exist ❌
    └── reports are lost ❌
```

### Why Reports Are Lost

1. User submits report on Render
2. Report written to `/tmp/geosafe.db` (ephemeral per-instance storage)
3. Instance shuts down after 15 minutes of inactivity
4. `/tmp` is deleted
5. Report is gone forever (no backup, no admin access)

---

## What's Required to Fix This

### Option 1: Keep Admin Local Only (Current)
- **Status:** ✅ Works locally, ❌ production broken
- **Cost:** $0 additional
- **Effort:** Low
- **Limitations:** Can't manage reports on production

### Option 2: Deploy Admin to Render (Recommended)
Would require:
- ✅ Switch from SQLite to PostgreSQL (shared database)
- ✅ Deploy admin dashboard as separate Web Service on Render
- ✅ Add authentication & authorization for production
- ✅ Set environment variables for both public & admin pointing to same DB
- ⏳ Estimated effort: 2-4 hours

**Result:** Reports persisted, admins can manage them remotely ✅

### Option 3: Hybrid Approach (Production Ready)
- Admin dashboard remains local-only
- Reports queued to a message service (SQS, PubSub)
- Separate backend processes and persists them
- Admins access via authenticated dashboard
- **Estimated effort:** 4-6 hours

---

## Recommendations

### Immediate (MVP)
Keep local-only admin, but:
1. Document that reports don't persist on Render
2. Advise users: "Reports submitted here are for live feedback only"
3. Use [UptimeRobot](https://uptimerobot.com) to keep Render warm (prevents data loss from cold starts)

### Short Term (1-2 weeks)
1. Deploy admin dashboard to Render
2. Switch to PostgreSQL (already have the code)
3. Users can submit reports, admins can manage them

### Long Term (Production)
1. Add role-based access control (RBAC)
2. Implement HTTPS + managed authentication
3. Add 2FA for admins
4. Set up automated backups
5. Create admin user management system

---

## Current Local Functionality (Confirmed)

| Feature | Status | Details |
|---------|--------|---------|
| Edit evacuation centers | ✅ | Stored in admin-dev.db, publishable to public db |
| Publish changes | ✅ | Syncs to data/geosafe.db, audit-logged |
| Receive reports (local) | ✅ | Public app → admin app via shared db |
| Triage reports | ✅ | Status: new/acknowledged/resolved, audit-logged |
| Photo uploads (centers) | ✅ | Stored in admin-uploads/ |
| Photo uploads (reports) | ✅ | Stored alongside reports |
| Analytics | ✅ | Visitor tracking & 7-day graph |
| Audit logs | ✅ | All changes recorded in admin_audit_log |
| Receive reports (Render) | ❌ | Lost on cold restart |
| Manage reports (Render) | ❌ | No admin dashboard deployed |

---

## Next Steps

**What would you like to do?**

1. **Deploy admin to Render now** - Make it production-ready
2. **Keep local-only** - Document limitations, focus on MVP
3. **Test locally first** - Set up and run locally before deciding
4. **Something else** - Other priorities?
