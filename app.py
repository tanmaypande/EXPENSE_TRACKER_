import os
import sys
from flask import Flask
from models.database import init_db
from routes import register_routes

# Ensure Windows cp1252 doesn't crash on standard logging
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "shopledger_master_secret_key_884920")

# Initialize and migrate commercial database
init_db()

# Register all modular POS & Shop Management routes
register_routes(app)

@app.before_request
def check_session_security():
    from flask import session, redirect, url_for, flash, request
    user_id = session.get("user_id")
    if user_id:
        endpoint = request.endpoint or ""
        # Skip static assets and authentication endpoints
        if endpoint.startswith("static") or endpoint in ("auth.logout", "super_admin.logout", "super_admin.login", "auth.login", "auth.first_login_password"):
            return

        # Super Admin is exempt from shop-level suspension checks
        if session.get("user_role") == "SUPER_ADMIN":
            return

        # Require password change on first login before allowing access
        if session.get("must_change_password"):
            return redirect(url_for("auth.first_login_password"))

        # Verify shop owner account status and session version
        from models.database import get_db_connection
        conn = get_db_connection()
        user_row = conn.execute("SELECT account_status, session_version FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()

        if not user_row or user_row["account_status"] in ("disabled", "suspended", "deactivated"):
            session.clear()
            flash("Your shop account has been disabled by the administrator. Access revoked.", "error")
            return redirect(url_for("auth.login"))

        stored_ver = session.get("session_version")
        if stored_ver is not None and user_row["session_version"] != stored_ver:
            session.clear()
            flash("Your session was terminated due to administrative security updates. Please sign in again.", "warning")
            return redirect(url_for("auth.login"))

@app.context_processor
def inject_global_data():
    from flask import session
    biz_id = session.get("business_id")
    if biz_id:
        try:
            from services.udhar_service import get_notifications
            notifs = get_notifications(biz_id, status_filter="unread", limit=1)
            return {"unread_notifications_count": notifs.get("unread_count", 0)}
        except Exception:
            return {"unread_notifications_count": 0}
    return {"unread_notifications_count": 0}

if __name__ == "__main__":
    app.run(debug=True)
