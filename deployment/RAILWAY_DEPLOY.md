# 🚂 Railway Deployment Guide — Face Attendance System

## How It Works

```
Your College PC                         Railway Cloud (free)
─────────────────                       ──────────────────────────────
📷 capture_faces.py  ──── internet ───→  🗄️  MySQL Database
📷 take_attendance.py ─── internet ───→       ↑
                                         🌐  Flask Web App
Any browser anywhere ──── internet ───→  (your-app.railway.app)
```

- Camera scripts run **locally** on the college PC (need webcam)
- Web dashboard + database run **on Railway** (accessible anywhere)
- Both share the same Railway MySQL database

---

## Step 1 — Push code to GitHub

Railway deploys from GitHub. Do this once:

```bash
# In your face_attendance folder
git init
git add .
git commit -m "Initial commit"

# Create a repo on github.com, then:
git remote add origin https://github.com/YOUR_USERNAME/face-attendance.git
git push -u origin main
```

> ✅ The `.gitignore` already excludes `.env`, `face_data/`, `trained_model/` — your secrets and face photos won't be uploaded.

---

## Step 2 — Create Railway account & project

1. Go to **[railway.app](https://railway.app)** → Sign up with GitHub
2. Click **New Project**
3. Select **Deploy from GitHub repo**
4. Select your `face-attendance` repository
5. Railway detects Python automatically — click **Deploy**

---

## Step 3 — Add MySQL Database

1. In your Railway project, click **+ New Service**
2. Select **Database → MySQL**
3. Railway creates a MySQL instance automatically
4. Click on the MySQL service → **Variables** tab
5. Copy the `MYSQL_URL` value (looks like `mysql://user:pass@host.railway.app:3306/railway`)

---

## Step 4 — Set Environment Variables for Flask app

1. Click on your **Flask web service** (not the MySQL one)
2. Go to **Variables** tab
3. Add these variables:

| Variable | Value |
|----------|-------|
| `MYSQL_URL` | paste the value copied from MySQL service |
| `SECRET_KEY` | run `python3 -c "import secrets; print(secrets.token_hex(32))"` and paste result |
| `FLASK_ENV` | `production` |

---

## Step 5 — Initialise the Database Schema

Railway won't auto-run your `database.sql`. Do it once:

### Option A — Railway CLI (easiest)
```bash
# Install Railway CLI
npm install -g @railway/cli        # or: brew install railway

# Login
railway login

# Run the SQL file against your Railway MySQL
railway run mysql -h $MYSQLHOST -u $MYSQLUSER -p$MYSQLPASSWORD $MYSQLDATABASE < database.sql
```

### Option B — MySQL Workbench / DBeaver (GUI)
1. In Railway → MySQL service → **Connect** tab → copy the connection details
2. Open MySQL Workbench → New Connection → paste host, port, user, password
3. Open and run `database.sql`

### Option C — Add an init route (temporary)
Add this to `app.py` temporarily, visit the URL once, then remove it:
```python
@app.route('/init-db-once')
def init_db_route():
    from db import init_db
    init_db()
    return "DB initialised!"
```

---

## Step 6 — Your app is live! 🎉

Railway gives you a URL like:  
**`https://face-attendance-production.up.railway.app`**

Find it: Railway project → your web service → **Settings** → **Domains**

Login with: `admin / admin123` (then reset the password)

---

## Step 7 — Connect local camera scripts to cloud DB

On your **college PC**, create a `.env` file in the project folder:

```bash
# face_attendance/.env  (on your local machine)
MYSQL_URL=mysql://user:password@host.railway.app:3306/railway
```

Paste your Railway MySQL URL here. Now the scripts write directly to the cloud:

```bash
# Capture face samples (runs local webcam, saves to cloud DB)
python capture_faces.py --id 3 --roll MCA2024001

# Take attendance (runs local webcam, marks attendance in cloud DB)
python take_attendance.py --session 5
```

---

## Step 8 — Re-deploy after code changes

Just push to GitHub — Railway auto-deploys:

```bash
git add .
git commit -m "Fix: updated something"
git push
```

Railway detects the push and redeploys in ~2 minutes.

---

## Railway Free Tier Limits

| Resource | Free Tier |
|----------|-----------|
| Execution hours | 500 hrs/month (~21 days) |
| RAM | 512 MB |
| MySQL storage | 1 GB |
| Bandwidth | 100 GB |
| Custom domain | ✅ Supported |
| Sleep on inactivity | No (always on) |

> **Hobby plan** is $5/month for unlimited hours if you exceed the free tier.

---

## Troubleshooting

**App not starting on Railway?**  
→ Railway dashboard → your service → **Logs** tab — check for Python errors

**Database connection error?**  
→ Make sure `MYSQL_URL` variable is set on the Flask service (not just the MySQL service)  
→ Check the URL format: `mysql://user:pass@host:port/dbname`

**"Table doesn't exist" error?**  
→ You haven't run `database.sql` yet — follow Step 5

**Camera scripts can't connect to Railway DB?**  
→ Make sure `.env` on your local machine has `MYSQL_URL` set  
→ Railway MySQL allows external connections by default

**Slow cold start?**  
→ Normal on free tier. First request after inactivity may take 5–10 seconds.

---

## Useful Railway CLI Commands

```bash
# View live logs
railway logs

# Open your app in browser  
railway open

# Run a command in the Railway environment
railway run python -c "from db import init_db; init_db()"

# List all environment variables
railway variables
```
