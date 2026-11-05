from flask import Blueprint, render_template, session, redirect, url_for
from services.report_service import get_dashboard_metrics
from services.business_service import get_business_by_id

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/")
def root():
    if "user_id" in session:
        if not session.get("business_id"):
            return redirect(url_for("auth.onboarding"))
        return redirect(url_for("dashboard.index"))
    return redirect(url_for("auth.login"))

@dashboard_bp.route("/dashboard")
def index():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    if not biz_id:
        return redirect(url_for("auth.onboarding"))

    business = get_business_by_id(biz_id)
    if not business:
        return redirect(url_for("auth.onboarding"))

    metrics = get_dashboard_metrics(biz_id)

    return render_template(
        "dashboard/index.html",
        business=business,
        metrics=metrics,
        user_name=session.get("user_name", "Shopkeeper"),
        user_role=session.get("user_role", "owner")
    )
