"""Security helpers: sign-in rules, access checks, CSRF and the audit log."""

import secrets
from datetime import datetime, timezone
from functools import wraps

from flask import abort, redirect, request, session, url_for

COMMON_PASSWORDS = {"password", "password1", "12345678", "123456789", "qwerty123", "11111111", "iloveyou", "abc12345"}


def password_problem(password):
    """Return why a password is not allowed, or None if it is fine (SR-1.1)."""
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if password.lower() in COMMON_PASSWORDS:
        return "This password is too common. Please choose another."
    return None


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapper


def admin_required(view):
    """Checks the role on the server for every admin page and action (SR-6.1)."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            abort(403)
        return view(*args, **kwargs)

    return wrapper


def check_csrf_token():
    """Every form that changes data must send back the token we issued (SR-G4)."""
    session.setdefault("csrf_token", secrets.token_hex(16))
    if request.method == "POST":
        if not secrets.compare_digest(request.form.get("csrf_token", ""), session["csrf_token"]):
            abort(400)


def audit(conn, action):
    """Record who did what, and when (SR-6.2)."""
    conn.execute(
        "INSERT INTO audit_log (created, user_id, action) VALUES (?, ?, ?)",
        (datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), session.get("user_id"), action),
    )
