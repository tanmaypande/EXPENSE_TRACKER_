import json
from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
from services.supplier_service import (
    get_suppliers, get_supplier_by_id, get_supplier_details, 
    create_supplier, update_supplier, delete_supplier, 
    create_purchase, get_purchases
)
from services.product_service import get_products
from services.business_service import get_business_by_id

supplier_bp = Blueprint("suppliers", __name__)

@supplier_bp.route("/suppliers")
def index():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    if not biz_id:
        return redirect(url_for("auth.onboarding"))

    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "all").strip().lower()

    suppliers = get_suppliers(biz_id, search=search, status_filter=status_filter, limit=150)
    business = get_business_by_id(biz_id)

    # Compute overall supplier metrics
    all_suppliers = get_suppliers(biz_id, limit=500)
    total_suppliers = len(all_suppliers)
    active_suppliers = sum(1 for s in all_suppliers if (s.get("total_purchases_count") or 0) > 0)
    total_purchases_val = sum((s.get("total_purchases") or 0.0) for s in all_suppliers)
    outstanding_payables = sum((s.get("outstanding_balance") or 0.0) for s in all_suppliers if (s.get("outstanding_balance") or 0.0) > 0)

    return render_template(
        "suppliers/list.html",
        suppliers=suppliers,
        business=business,
        search=search,
        status_filter=status_filter,
        total_suppliers=total_suppliers,
        active_suppliers=active_suppliers,
        total_purchases_val=round(total_purchases_val, 2),
        outstanding_payables=round(outstanding_payables, 2)
    )

@supplier_bp.route("/suppliers/add", methods=["POST"])
def add_supplier():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    name = request.form.get("name", "").strip()
    contact = request.form.get("contact_person", "").strip()
    phone = request.form.get("phone", "").strip()
    email = request.form.get("email", "").strip()
    address = request.form.get("address", "").strip()
    gstin = request.form.get("gstin", "").strip()

    create_supplier(biz_id, name=name, contact_person=contact, phone=phone, email=email, address=address, gstin=gstin)
    return redirect(url_for("suppliers.index"))

@supplier_bp.route("/suppliers/<int:id>")
def supplier_detail(id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    data = get_supplier_details(id, biz_id)
    if not data:
        return "Supplier not found", 404

    business = get_business_by_id(biz_id)
    return render_template(
        "suppliers/detail.html",
        supplier=data["supplier"],
        purchases=data["purchases"],
        total_inward_value=data["total_inward_value"],
        total_paid_value=data["total_paid_value"],
        total_due_value=data["total_due_value"],
        total_po_count=data["total_po_count"],
        business=business
    )

@supplier_bp.route("/suppliers/edit/<int:id>", methods=["POST"])
def edit_supplier(id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    name = request.form.get("name", "").strip()
    contact = request.form.get("contact_person", "").strip()
    phone = request.form.get("phone", "").strip()
    email = request.form.get("email", "").strip()
    address = request.form.get("address", "").strip()
    gstin = request.form.get("gstin", "").strip()

    update_supplier(biz_id, id, name=name, contact_person=contact, phone=phone, email=email, address=address, gstin=gstin)
    return redirect(request.referrer or url_for("suppliers.index"))

@supplier_bp.route("/suppliers/delete/<int:id>", methods=["POST", "GET"])
def delete_supplier_route(id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    delete_supplier(biz_id, id)
    return redirect(url_for("suppliers.index"))

@supplier_bp.route("/purchases")
def list_purchases():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    purchases = get_purchases(biz_id)
    business = get_business_by_id(biz_id)

    return render_template(
        "suppliers/purchases.html",
        purchases=purchases,
        business=business
    )

@supplier_bp.route("/purchases/new", methods=["GET", "POST"])
def new_purchase():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    suppliers = get_suppliers(biz_id)
    products = get_products(biz_id, limit=200)
    business = get_business_by_id(biz_id)

    if request.method == "POST":
        supplier_id = request.form.get("supplier_id")
        if supplier_id:
            try: supplier_id = int(supplier_id)
            except ValueError: supplier_id = None

        purchase_no = request.form.get("purchase_number", "").strip() or f"PO-{session['user_id']}"
        payment_method = request.form.get("payment_method", "cash")
        paid_amount = float(request.form.get("paid_amount", 0.0) or 0.0)
        notes = request.form.get("notes", "")

        # Items payload parsed from JSON
        raw_items = request.form.get("purchase_items_json")
        items = json.loads(raw_items) if raw_items else []

        if items:
            create_purchase(biz_id, supplier_id, purchase_no, items, paid_amount=paid_amount, payment_method=payment_method, notes=notes)
            return redirect(url_for("suppliers.list_purchases"))

    return render_template(
        "suppliers/new_purchase.html",
        suppliers=suppliers,
        products=products,
        business=business
    )
