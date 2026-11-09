from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from services.product_service import (
    get_products, get_product_by_id, create_product, update_product, 
    adjust_stock, get_stock_movements, get_categories, create_category,
    delete_product
)
from services.business_service import get_business_by_id

inventory_bp = Blueprint("inventory", __name__)

@inventory_bp.route("/inventory")
@inventory_bp.route("/products")
@inventory_bp.route("/catalog")
@inventory_bp.route("/catalogue")
def list_products():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    if not biz_id:
        return redirect(url_for("auth.onboarding"))

    search = request.args.get("search", "").strip()
    category_id = request.args.get("category_id")
    low_stock = request.args.get("low_stock") == "1"

    if category_id:
        try: category_id = int(category_id)
        except ValueError: category_id = None

    products = get_products(biz_id, search=search, category_id=category_id, low_stock=low_stock, limit=100)
    categories = get_categories(biz_id)
    business = get_business_by_id(biz_id)

    return render_template(
        "inventory/list.html",
        products=products,
        categories=categories,
        business=business,
        search=search,
        selected_category=category_id,
        low_stock=low_stock
    )

@inventory_bp.route("/inventory/add", methods=["GET", "POST"])
def add_product():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    categories = get_categories(biz_id)
    business = get_business_by_id(biz_id)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        sku = request.form.get("sku", "").strip()
        barcode = request.form.get("barcode", "").strip()
        cat_id = request.form.get("category_id")
        brand = request.form.get("brand", "").strip()
        cost_price = float(request.form.get("purchase_price", 0.0) or 0.0)
        sell_price = float(request.form.get("selling_price", 0.0) or 0.0)
        tax_rate = float(request.form.get("tax_rate", 0.0) or 0.0)
        stock_qty = float(request.form.get("stock_quantity", 0.0) or 0.0)
        min_stock = float(request.form.get("min_stock_level", 5.0) or 5.0)
        unit = request.form.get("unit", "pcs").strip() or "pcs"
        desc = request.form.get("description", "").strip()

        if cat_id:
            try: cat_id = int(cat_id)
            except ValueError: cat_id = None

        create_product(
            business_id=biz_id,
            name=name,
            sku=sku,
            barcode=barcode,
            category_id=cat_id,
            brand=brand,
            purchase_price=cost_price,
            selling_price=sell_price,
            tax_rate=tax_rate,
            stock_quantity=stock_qty,
            min_stock_level=min_stock,
            unit=unit,
            description=desc
        )
        return redirect(url_for("inventory.list_products"))

    return render_template("inventory/form.html", categories=categories, business=business, product=None)

@inventory_bp.route("/inventory/edit/<int:id>", methods=["GET", "POST"])
def edit_product(id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    product = get_product_by_id(id, biz_id)
    if not product:
        return "Product not found", 404

    categories = get_categories(biz_id)
    business = get_business_by_id(biz_id)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        sku = request.form.get("sku", "").strip()
        barcode = request.form.get("barcode", "").strip()
        cat_id = request.form.get("category_id")
        brand = request.form.get("brand", "").strip()
        cost_price = float(request.form.get("purchase_price", 0.0) or 0.0)
        sell_price = float(request.form.get("selling_price", 0.0) or 0.0)
        tax_rate = float(request.form.get("tax_rate", 0.0) or 0.0)
        min_stock = float(request.form.get("min_stock_level", 5.0) or 5.0)
        unit = request.form.get("unit", "pcs").strip() or "pcs"
        desc = request.form.get("description", "").strip()

        if cat_id:
            try: cat_id = int(cat_id)
            except ValueError: cat_id = None

        update_product(
            product_id=id,
            business_id=biz_id,
            name=name,
            sku=sku,
            barcode=barcode,
            category_id=cat_id,
            brand=brand,
            purchase_price=cost_price,
            selling_price=sell_price,
            tax_rate=tax_rate,
            min_stock_level=min_stock,
            unit=unit,
            description=desc
        )
        return redirect(url_for("inventory.list_products"))

    return render_template("inventory/form.html", categories=categories, business=business, product=product)

@inventory_bp.route("/inventory/adjust", methods=["POST"])
def stock_adjustment():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    product_id = int(request.form.get("product_id"))
    qty = float(request.form.get("quantity", 0.0) or 0.0)
    reason = request.form.get("reason", "adjustment")
    notes = request.form.get("notes", "")

    adjust_stock(biz_id, product_id, qty, reason=reason, notes=notes)
    return redirect(url_for("inventory.list_products"))

@inventory_bp.route("/inventory/movements")
def stock_history():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    movements = get_stock_movements(biz_id, limit=80)
    business = get_business_by_id(biz_id)

    return render_template("inventory/movements.html", movements=movements, business=business)

@inventory_bp.route("/inventory/category/add", methods=["POST"])
def add_category():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    name = request.form.get("category_name", "").strip()
    desc = request.form.get("category_desc", "").strip()
    if name:
        create_category(biz_id, name, desc)
    return redirect(url_for("inventory.list_products"))

@inventory_bp.route("/inventory/delete/<int:id>", methods=["POST"])
@inventory_bp.route("/products/delete/<int:id>", methods=["POST"])
def remove_product(id):
    is_ajax = request.is_json or "application/json" in request.headers.get("Accept", "") or request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if "user_id" not in session:
        if is_ajax:
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    if not biz_id:
        if is_ajax:
            return jsonify({"success": False, "error": "No business profile"}), 400
        return redirect(url_for("auth.onboarding"))

    try:
        result = delete_product(biz_id, id)
        if is_ajax:
            return jsonify(result)
        flash(result["message"], "success")
        return redirect(url_for("inventory.list_products"))
    except ValueError as ve:
        if is_ajax:
            return jsonify({"success": False, "error": str(ve)}), 404
        flash(str(ve), "error")
        return redirect(url_for("inventory.list_products"))
    except Exception as e:
        if is_ajax:
            return jsonify({"success": False, "error": f"Failed to delete product: {str(e)}"}), 500
        flash(f"Error: {str(e)}", "error")
        return redirect(url_for("inventory.list_products"))
