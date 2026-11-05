from flask import Blueprint, render_template, request, session, redirect, url_for
from services.customer_service import get_customers, get_customer_ledger, record_customer_payment, create_or_get_customer
from services.business_service import get_business_by_id

customer_bp = Blueprint("customers", __name__)

@customer_bp.route("/customers")
def index():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    if not biz_id:
        return redirect(url_for("auth.onboarding"))

    search = request.args.get("search", "").strip()
    customers = get_customers(biz_id, search=search, limit=100)
    business = get_business_by_id(biz_id)

    return render_template(
        "customers/list.html",
        customers=customers,
        business=business,
        search=search
    )

@customer_bp.route("/customers/add", methods=["POST"])
def add():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    email = request.form.get("email", "").strip()
    address = request.form.get("address", "").strip()
    gstin = request.form.get("gstin", "").strip()

    create_or_get_customer(biz_id, name=name, phone=phone, email=email, address=address, gstin=gstin)
    return redirect(url_for("customers.index"))

@customer_bp.route("/customers/<int:id>/ledger")
def ledger(id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    data = get_customer_ledger(id, biz_id)
    if not data:
        return "Customer not found", 404

    business = get_business_by_id(biz_id)
    return render_template(
        "customers/ledger.html",
        customer=data["customer"],
        invoices=data["invoices"],
        payments=data["payments"],
        business=business
    )

@customer_bp.route("/customers/<int:id>/pay", methods=["POST"])
def pay(id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    amount = float(request.form.get("amount", 0.0) or 0.0)
    method = request.form.get("payment_method", "cash")
    notes = request.form.get("notes", "")

    record_customer_payment(biz_id, id, amount, payment_method=method, notes=notes)
    return redirect(url_for("customers.ledger", id=id))
