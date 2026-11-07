from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify, flash
from services.udhar_service import (
    get_udhar_summary,
    get_udhar_invoices,
    collect_udhar_payment,
    get_customer_udhar_ledger,
    run_udhar_reminders,
    get_notifications,
    mark_notification_read,
    snooze_notification
)
from services.business_service import get_business_by_id

udhar_bp = Blueprint("udhar", __name__)

@udhar_bp.route("/udhar")
def index():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    if not biz_id:
        return redirect(url_for("auth.onboarding"))

    # Auto-evaluate 5-day cycle reminders for this business
    try:
        run_udhar_reminders(biz_id)
    except Exception:
        pass

    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "all")
    sort_by = request.args.get("sort", "balance_desc")

    business = get_business_by_id(biz_id)
    summary = get_udhar_summary(biz_id)
    invoices = get_udhar_invoices(biz_id, search=search, status_filter=status_filter, sort_by=sort_by)

    return render_template(
        "udhar/index.html",
        business=business,
        summary=summary,
        invoices=invoices,
        search=search,
        status_filter=status_filter,
        sort_by=sort_by
    )

@udhar_bp.route("/udhar/collect", methods=["POST"])
def collect_payment():
    if "user_id" not in session:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    biz_id = session.get("business_id")
    if not biz_id:
        return jsonify({"success": False, "error": "No business selected"}), 400

    is_json = request.is_json
    data = request.get_json(silent=True) if is_json else request.form

    try:
        invoice_id = int(data.get("invoice_id"))
        amount = float(data.get("amount", 0.0))
        payment_method = str(data.get("payment_method", "cash")).strip().lower()
        transaction_ref = str(data.get("transaction_reference", "")).strip()
        notes = str(data.get("notes", "")).strip()

        result = collect_udhar_payment(
            business_id=biz_id,
            invoice_id=invoice_id,
            amount=amount,
            payment_method=payment_method,
            notes=notes,
            transaction_ref=transaction_ref
        )

        if is_json:
            return jsonify(result)

        flash(f"Successfully collected ₹{amount:,.2f} against {result['invoice_number']}! Remaining due: ₹{result['new_balance']:,.2f}", "success")
        return redirect(request.referrer or url_for("udhar.index"))

    except ValueError as ve:
        if is_json:
            return jsonify({"success": False, "error": str(ve)}), 400
        flash(str(ve), "error")
        return redirect(request.referrer or url_for("udhar.index"))
    except Exception as e:
        if is_json:
            return jsonify({"success": False, "error": f"Failed to record collection: {str(e)}"}), 500
        flash(f"Error: {str(e)}", "error")
        return redirect(request.referrer or url_for("udhar.index"))

@udhar_bp.route("/udhar/customer/<int:customer_id>")
def customer_ledger(customer_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    if not biz_id:
        return redirect(url_for("auth.onboarding"))

    business = get_business_by_id(biz_id)
    ledger = get_customer_udhar_ledger(biz_id, customer_id)

    if not ledger:
        flash("Customer not found or access denied.", "error")
        return redirect(url_for("udhar.index"))

    return render_template(
        "udhar/customer_ledger.html",
        business=business,
        ledger=ledger
    )

@udhar_bp.route("/notifications")
def notifications_view():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    if not biz_id:
        return redirect(url_for("auth.onboarding"))

    # Auto-run 5-day cycle check
    try:
        run_udhar_reminders(biz_id)
    except Exception:
        pass

    status_filter = request.args.get("filter", "all")
    business = get_business_by_id(biz_id)
    data = get_notifications(biz_id, status_filter=status_filter, limit=100)

    return render_template(
        "notifications/index.html",
        business=business,
        notifications=data["notifications"],
        unread_count=data["unread_count"],
        status_filter=status_filter
    )

@udhar_bp.route("/notifications/<int:notification_id>/read", methods=["POST"])
def mark_read(notification_id):
    if "user_id" not in session:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    biz_id = session.get("business_id")
    mark_notification_read(biz_id, notification_id)
    return jsonify({"success": True})

@udhar_bp.route("/notifications/<int:notification_id>/snooze", methods=["POST"])
def snooze(notification_id):
    if "user_id" not in session:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    biz_id = session.get("business_id")
    days = 5
    if request.is_json and request.json.get("days"):
        days = int(request.json.get("days"))
    snooze_notification(biz_id, notification_id, days=days)
    return jsonify({"success": True})

@udhar_bp.route("/notifications/run-reminders", methods=["POST"])
def trigger_reminders():
    if "user_id" not in session:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    biz_id = session.get("business_id")
    created = run_udhar_reminders(biz_id)
    return jsonify({"success": True, "created_reminders": created})
