import hashlib
import hmac
import os
import re
import secrets
import time
from datetime import timedelta
from functools import wraps
from urllib.parse import quote, urlencode, urlparse

from dotenv import load_dotenv
from flask import (Flask, jsonify, make_response, redirect, render_template,
                   request, session, url_for)
from sqlalchemy import case, func, text
from werkzeug.middleware.proxy_fix import ProxyFix

from model import Visit, db, lagos_day, utcnow

load_dotenv()

DEFAULT_PLAY_URL = "https://play.google.com/store/apps/details?id=com.cbt.jambixo"

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

db_url = os.environ.get("DATABASE_URL", "sqlite:///jambixo.db")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
    SQLALCHEMY_DATABASE_URI=db_url,
    SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True, "pool_recycle": 280},
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("FLASK_DEBUG") != "1",
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
)

PLAY_URL = os.environ.get("PLAY_STORE_URL", DEFAULT_PLAY_URL)
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
REDIRECT_DELAY_MS = int(os.environ.get("REDIRECT_DELAY_MS", "1800"))

db.init_app(app)
with app.app_context():
    db.create_all()

BOT_RE = re.compile(
    r"bot|crawl|spider|slurp|preview|headless|facebookexternalhit|python|curl|wget|"
    r"monitor|uptime|go-http|okhttp/|java/|httpclient|scrapy|lighthouse|cron",
    re.I,
)


# ---------------------------------------------------------------- helpers
def clean(value, limit=80):
    value = re.sub(r"[^\w\-\. ]", "", (value or "").strip())[:limit]
    return value or ""


def detect_device(ua):
    u = ua.lower()
    if "android" in u:
        return "Android"
    if "iphone" in u or "ipad" in u or "ipod" in u:
        return "iPhone/iPad"
    if "windows" in u:
        return "Windows"
    if "mac os" in u or "macintosh" in u:
        return "Mac"
    if "linux" in u:
        return "Linux"
    return "Other"


def detect_app(ua):
    if re.search(r"musical_ly|bytedance|tiktok|trill", ua, re.I):
        return "TikTok app"
    if re.search(r"FBAN|FBAV|FB_IAB", ua):
        return "Facebook app"
    if "Instagram" in ua:
        return "Instagram app"
    if "WhatsApp" in ua:
        return "WhatsApp"
    return "Browser"


def build_play_url(campaign, source, medium):
    """Adds a Play Store referrer so installs show up per campaign in Play Console."""
    if "referrer=" in PLAY_URL:
        return PLAY_URL
    ref = urlencode({"utm_source": source, "utm_medium": medium, "utm_campaign": campaign})
    sep = "&" if "?" in PLAY_URL else "?"
    return f"{PLAY_URL}{sep}referrer={quote(ref, safe='')}"


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


def csrf_ok():
    sent = request.form.get("csrf", "")
    return bool(sent) and hmac.compare_digest(sent, session.get("csrf", ""))


app.jinja_env.globals["csrf_token"] = csrf_token

_failed = {}  # ip -> list of failed login timestamps


def login_blocked(ip):
    now = time.time()
    _failed[ip] = [t for t in _failed.get(ip, []) if now - t < 600]
    return len(_failed[ip]) >= 5


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)

    return wrapper


# ---------------------------------------------------------------- public pages
@app.route("/")
@app.route("/go")
@app.route("/c/<campaign>")
def landing(campaign=None):
    ua = request.headers.get("User-Agent", "")
    in_app = detect_app(ua)
    camp = clean(campaign or request.args.get("utm_campaign") or request.args.get("campaign")) or "direct"

    src = clean(request.args.get("utm_source") or request.args.get("source"))
    if not src:
        ref_host = urlparse(request.referrer or "").netloc.replace("www.", "")
        src = "tiktok" if in_app == "TikTok app" else (clean(ref_host) or "direct")
    medium = clean(request.args.get("utm_medium")) or "redirect"

    ip = request.remote_addr or ""
    day = lagos_day()
    visitor = hashlib.sha256(f"{app.config['SECRET_KEY']}|{day}|{ip}|{ua}".encode()).hexdigest()[:20]

    visit_id = ""
    try:
        visit = Visit(
            day=day,
            campaign=camp,
            source=src,
            device=detect_device(ua),
            app=in_app,
            country=(request.headers.get("CF-IPCountry") or "")[:8],
            visitor_hash=visitor,
            is_bot=(not ua) or bool(BOT_RE.search(ua)),
        )
        db.session.add(visit)
        db.session.commit()
        visit_id = visit.id
    except Exception:
        db.session.rollback()

    resp = make_response(render_template(
        "landing.html",
        play_url=build_play_url(camp, src, medium),
        visit_id=visit_id,
        delay_ms=REDIRECT_DELAY_MS,
    ))
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/api/redirected", methods=["POST"])
def redirected():
    data = request.get_json(force=True, silent=True) or {}
    try:
        vid = int(data.get("id"))
        Visit.query.filter_by(id=vid).update({"redirected": True})
        db.session.commit()
    except Exception:
        db.session.rollback()
    return "", 204


@app.route("/health", methods=["GET", "HEAD"])
def health():
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify(status="ok")
    except Exception:
        db.session.rollback()
        return jsonify(status="database error"), 503


# ---------------------------------------------------------------- admin
@app.route("/admin/login", methods=["GET", "POST"])
def login():
    if session.get("admin"):
        return redirect(url_for("dashboard"))
    error = None
    if request.method == "POST":
        ip = request.remote_addr or ""
        if not ADMIN_EMAIL or not ADMIN_PASSWORD:
            error = "Admin login is not set up. Add ADMIN_EMAIL and ADMIN_PASSWORD."
        elif login_blocked(ip):
            error = "Too many attempts. Please wait a few minutes."
        elif not csrf_ok():
            error = "Session expired. Please try again."
        else:
            email = request.form.get("email", "").strip().lower().encode()
            pw = request.form.get("password", "").encode()
            ok_email = hmac.compare_digest(email, ADMIN_EMAIL.strip().lower().encode())
            ok_pw = hmac.compare_digest(pw, ADMIN_PASSWORD.encode())
            if ok_email and ok_pw:
                session.clear()
                session["admin"] = True
                session.permanent = True
                return redirect(url_for("dashboard"))
            _failed.setdefault(ip, []).append(time.time())
            error = "Wrong email or password."
    return render_template("login.html", error=error)


@app.route("/admin/logout", methods=["POST"])
def logout():
    if csrf_ok():
        session.clear()
    return redirect(url_for("login"))


def breakdown(column, base, limit=8):
    rows = (
        db.session.query(column, func.count(Visit.id))
        .filter(*base)
        .group_by(column)
        .order_by(func.count(Visit.id).desc())
        .limit(limit)
        .all()
    )
    top = max([r[1] for r in rows], default=1)
    return [{"label": r[0] or "Unknown", "count": r[1], "pct": round(r[1] * 100 / top)} for r in rows]


@app.route("/admin")
@admin_required
def dashboard():
    try:
        days = int(request.args.get("days", 7))
    except ValueError:
        days = 7
    if days not in (1, 7, 14, 30, 90):
        days = 7
    include_bots = request.args.get("bots") == "1"

    today = lagos_day()
    start = (utcnow() + timedelta(hours=1) - timedelta(days=days - 1)).date().isoformat()
    base = [Visit.day >= start]
    if not include_bots:
        base.append(Visit.is_bot.is_(False))

    daily_rows = (
        db.session.query(
            Visit.day,
            func.count(Visit.id),
            func.count(func.distinct(Visit.visitor_hash)),
            func.sum(case((Visit.redirected.is_(True), 1), else_=0)),
        )
        .filter(*base)
        .group_by(Visit.day)
        .all()
    )
    by_day = {r[0]: (r[1], r[2], int(r[3] or 0)) for r in daily_rows}
    series = []
    for i in range(days - 1, -1, -1):
        d = ((utcnow() + timedelta(hours=1)).date() - timedelta(days=i)).isoformat()
        v, u, r = by_day.get(d, (0, 0, 0))
        series.append({"day": d, "visits": v, "unique": u})

    total = sum(s["visits"] for s in series)
    unique = sum(s["unique"] for s in series)
    redirected = sum(v[2] for d, v in by_day.items())
    stats = {
        "total": total,
        "unique": unique,
        "today": by_day.get(today, (0, 0, 0))[0],
        "rate": round(redirected * 100 / total) if total else 0,
        "all_time": Visit.query.filter_by(is_bot=False).count(),
        "bots": Visit.query.filter(Visit.day >= start, Visit.is_bot.is_(True)).count(),
    }

    recent_q = Visit.query
    if not include_bots:
        recent_q = recent_q.filter_by(is_bot=False)
    recent = recent_q.order_by(Visit.id.desc()).limit(30).all()

    return render_template(
        "dashboard.html",
        days=days,
        include_bots=include_bots,
        stats=stats,
        series=series,
        campaigns=breakdown(Visit.campaign, base),
        sources=breakdown(Visit.source, base),
        devices=breakdown(Visit.device, base),
        apps=breakdown(Visit.app, base),
        countries=breakdown(Visit.country, base),
        recent=recent,
        site_url=request.url_root.rstrip("/"),
    )


@app.errorhandler(404)
def not_found(_):
    if request.path.startswith(("/static", "/api")) or request.path.endswith((".ico", ".png", ".txt")):
        return "", 404
    return redirect(url_for("landing"))


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", port=int(os.environ.get("PORT", 5000)))
