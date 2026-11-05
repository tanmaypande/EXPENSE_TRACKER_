from flask import Blueprint, render_template, request, session, redirect, url_for
from services.invoice_service import get_invoice_details, get_recent_invoices
from services.business_service import get_business_by_id

invoice_bp = Blueprint("invoices", __name__)

@invoice_bp.route("/invoices")
def list_invoices():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    if not biz_id:
        return redirect(url_for("auth.onboarding"))

    business = get_business_by_id(biz_id)
    search = request.args.get("search", "").strip()
    invoices = get_recent_invoices(biz_id, limit=60, search=search)

    return render_template(
        "invoices/list.html",
        business=business,
        invoices=invoices,
        search=search
    )

@invoice_bp.route("/invoices/<int:id>")
def view_invoice(id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    invoice_data = get_invoice_details(biz_id, id)
    if not invoice_data:
        return "Invoice not found or unauthorized", 404

    return render_template(
        "invoices/view.html",
        sale=invoice_data["sale"],
        items=invoice_data["items"],
        business=get_business_by_id(biz_id)
    )

@invoice_bp.route("/invoices/<int:id>/print")
def print_invoice(id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    invoice_data = get_invoice_details(biz_id, id)
    if not invoice_data:
        return "Invoice not found or unauthorized", 404

    format_type = request.args.get("format", "thermal").lower() # 'thermal' or 'a4'

    return render_template(
        "invoices/print.html",
        sale=invoice_data["sale"],
        items=invoice_data["items"],
        business=get_business_by_id(biz_id),
        format_type=format_type
    )
