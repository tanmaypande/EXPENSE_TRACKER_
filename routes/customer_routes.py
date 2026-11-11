from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
from services.customer_service import (
    get_customers, get_customer_by_id, get_customer_ledger, 
    record_customer_payment, create_or_get_customer, update_customer, delete_customer
)
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
    status_filter = request.args.get("status", "all").strip().lower()
    sort_by = request.args.get("sort", "name_asc").strip().lower()

    customers = get_customers(biz_id, search=search, status_filter=status_filter, sort_by=sort_by, limit=150)
    business = get_business_by_id(biz_id)

    # Compute overall summary metrics across all customers (unfiltered)
    all_customers = get_customers(biz_id, limit=500)
    total_people = len(all_customers)
    total_due = sum((c.get("outstanding_balance") or 0.0) for c in all_customers if (c.get("outstanding_balance") or 0.0) > 0)
    accounts_with_due = sum(1 for c in all_customers if (c.get("outstanding_balance") or 0.0) > 0)
    clean_accounts = total_people - accounts_with_due

    return render_template(
        "customers/list.html",
        customers=customers,
        business=business,
        search=search,
        status_filter=status_filter,
        sort_by=sort_by,
        total_people=total_people,
        total_due=round(total_due, 2),
        accounts_with_due=accounts_with_due,
        clean_accounts=clean_accounts
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

@customer_bp.route("/customers/edit/<int:id>", methods=["POST"])
def edit(id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    email = request.form.get("email", "").strip()
    address = request.form.get("address", "").strip()
    gstin = request.form.get("gstin", "").strip()

    update_customer(biz_id, id, name=name, phone=phone, email=email, address=address, gstin=gstin)
    return redirect(url_for("customers.index"))

@customer_bp.route("/customers/delete/<int:id>", methods=["POST", "GET"])
def delete(id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    try:
        delete_customer(biz_id, id)
        flash("Customer removed successfully.", "success")
    except ValueError as ve:
        flash(str(ve), "error")
    except Exception as e:
        flash(f"Error removing customer: {str(e)}", "error")
    return redirect(url_for("customers.index"))

@customer_bp.route("/api/customers/<int:id>")
def get_customer_json(id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    biz_id = session.get("business_id")
    cust = get_customer_by_id(id, biz_id)
    if not cust:
        return jsonify({"error": "Not found"}), 404
    return jsonify(cust)

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
