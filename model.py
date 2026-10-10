from datetime import datetime, timedelta, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def lagos_day(dt=None):
    """Date string (YYYY-MM-DD) in Nigerian time (UTC+1)."""
    dt = dt or utcnow()
    return (dt + timedelta(hours=1)).date().isoformat()


class Visit(db.Model):
    """One visit to the landing link. No IP address is stored."""

    __tablename__ = "visits"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=utcnow, index=True)
    day = db.Column(db.String(10), index=True)  # Nigerian date, used for daily charts
    campaign = db.Column(db.String(80), default="direct", index=True)
    source = db.Column(db.String(80), default="direct")
    device = db.Column(db.String(20), default="other")
    app = db.Column(db.String(20), default="Browser")  # TikTok app, Facebook app, Browser...
    country = db.Column(db.String(8), default="")
    visitor_hash = db.Column(db.String(24), index=True)  # daily anonymous hash for unique counts
    is_bot = db.Column(db.Boolean, default=False, index=True)
    redirected = db.Column(db.Boolean, default=False)

    @property
    def local_time(self):
        return (self.created_at + timedelta(hours=1)).strftime("%d %b, %I:%M %p")
