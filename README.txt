JAMBIXO redirect and visit tracker

RENDER SETUP
1. Push these files to a GitHub repo, then create a Render Web Service from it.
2. Build command:  pip install -r requirements.txt
3. Start command:  gunicorn app:app
4. Environment variables (copy them from the .env file, do not upload .env to GitHub):
   SECRET_KEY, ADMIN_EMAIL, ADMIN_PASSWORD, DATABASE_URL, PLAY_STORE_URL (optional)
   DATABASE_URL = the Internal Database URL of a Render PostgreSQL database.
   If you skip DATABASE_URL, the app uses a file database that is erased on every redeploy.
5. Cron job ping: https://YOUR-SITE.onrender.com/health  (every 10 minutes)

LINKS
  /                    landing page, records the visit, then opens Google Play
  /c/tiktok1           same, but tags the visit with the campaign name tiktok1
  /admin               dashboard (sign in with ADMIN_EMAIL and ADMIN_PASSWORD)
  /health              health check for your cron job

Use a different /c/name for each ad so the dashboard shows which ad brings visits.
