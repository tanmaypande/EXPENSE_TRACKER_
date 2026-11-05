import json
from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
from services.product_service import get_products, get_categories, find_product_by_barcode_or_sku
from services.pos_service import complete_sale
from services.customer_service import get_customers, create_or_get_customer
from services.business_service import get_business_by_id

pos_bp = Blueprint("pos", __name__)

@pos_bp.route("/pos")
def index():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    if not biz_id:
        return redirect(url_for("auth.onboarding"))

    business = get_business_by_id(biz_id)
    products = get_products(biz_id, limit=60)
    categories = get_categories(biz_id)
    customers = get_customers(biz_id, limit=30)

    return render_template(
        "pos/index.html",
        business=business,
        products=products,
        categories=categories,
        customers=customers
    )

@pos_bp.route("/api/pos/products")
def api_products():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    biz_id = session.get("business_id")
    search = request.args.get("q", "").strip()
    category_id = request.args.get("category_id")
    if category_id:
        try: category_id = int(category_id)
        except ValueError: category_id = None

    products = get_products(biz_id, search=search, category_id=category_id, limit=50)
    return jsonify(products)

@pos_bp.route("/api/pos/barcode")
def api_barcode():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    biz_id = session.get("business_id")
    code = request.args.get("code", "").strip()
    prod = find_product_by_barcode_or_sku(biz_id, code)
    if prod:
        return jsonify({"found": True, "product": prod})
    return jsonify({"found": False})

@pos_bp.route("/pos/checkout", methods=["POST"])
def checkout():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    biz_id = session.get("business_id")
    business = get_business_by_id(biz_id)

    # Support JSON request payload (from interactive POS JS engine) or form submit
    if request.is_json:
        data = request.get_json()
    else:
        raw = request.form.get("checkout_data")
        data = json.loads(raw) if raw else {}

    items = data.get("items", [])
    if not items:
        return jsonify({"success": False, "error": "Cart is empty."}), 400

    customer_id = data.get("customer_id")
    customer_name = data.get("customer_name")
    customer_phone = data.get("customer_phone")

    # If customer phone or name provided without customer_id, auto-create/link customer
    if not customer_id and (customer_phone or (customer_name and customer_name != "Walk-in Customer")):
        cust = create_or_get_customer(biz_id, name=customer_name, phone=customer_phone)
        customer_id = cust["id"]
        customer_name = cust["name"]

    discount_amount = float(data.get("discount_amount", 0.0) or 0.0)
    payment_method = data.get("payment_method", "cash").lower()
    paid_amount = float(data.get("paid_amount", 0.0)) if data.get("paid_amount") is not None else None
    notes = data.get("notes", "")

    try:
        result = complete_sale(
            business_id=biz_id,
            user_id=session["user_id"],
            items=items,
            customer_id=customer_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            discount_amount=discount_amount,
            payment_method=payment_method,
            paid_amount=paid_amount,
            notes=notes,
            prefix=business.get("invoice_prefix", "INV-"),
            tax_enabled=business.get("tax_enabled", 1)
        )
        return jsonify({
            "success": True,
            "sale_id": result["sale_id"],
            "invoice_number": result["invoice_number"],
            "invoice_url": url_for("invoices.view_invoice", id=result["sale_id"]),
            "print_url": url_for("invoices.print_invoice", id=result["sale_id"])
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400
