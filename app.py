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
