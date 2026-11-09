from functools import wraps
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from services.auth_service import authenticate_user
from services.super_admin_service import (
    get_simple_metrics,
    get_all_shops,
    get_shop_details,
    create_shop_owner_and_business,
    update_shop_status,
    reset_shop_owner_password
)

super_admin_bp = Blueprint("super_admin", __name__, url_prefix="/super-admin")

def super_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session or session.get("user_role") != "SUPER_ADMIN":
            if request.is_json or "application/json" in request.headers.get("Accept", ""):
                return jsonify({"success": False, "error": "Forbidden: Super Administrator access required."}), 403
            flash("Super Administrator authentication required.", "error")
            return redirect(url_for("super_admin.login"))
        return f(*args, **kwargs)
    return decorated_function

# =========================================================================
# 1. SUPER ADMIN AUTHENTICATION
# =========================================================================

@super_admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session and session.get("user_role") == "SUPER_ADMIN":
        return redirect(url_for("super_admin.dashboard"))

    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = authenticate_user(email, password)
        if user and user.get("role") == "SUPER_ADMIN":
            session["user_id"] = user["id"]
            session["user_email"] = user["email"]
            session["user_name"] = user.get("name") or "Super Administrator"
            session["user_role"] = "SUPER_ADMIN"
            session["is_super_admin"] = True
            return redirect(url_for("super_admin.dashboard"))
        else:
            error = "Invalid Super Administrator credentials."

    return render_template("super_admin/login.html", error=error)

@super_admin_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("super_admin.login"))

# =========================================================================
# 2. SUPER ADMIN DASHBOARD (Clean 3-Metric Overview)
# =========================================================================

@super_admin_bp.route("")
@super_admin_bp.route("/dashboard")
@super_admin_required
def dashboard():
    metrics = get_simple_metrics()
    return render_template("super_admin/dashboard.html", metrics=metrics)

# =========================================================================
# 3. REGISTERED SHOPS LIST
# =========================================================================

@super_admin_bp.route("/shops")
@super_admin_required
def list_shops():
    search = request.args.get("search", "").strip()
    shops = get_all_shops(search=search)
    return render_template("super_admin/shops.html", shops=shops, search=search)

@super_admin_bp.route("/shops/<int:id>")
@super_admin_required
def shop_detail(id):
    shop = get_shop_details(id)
    if not shop:
        flash(f"Shop #{id} not found.", "error")
        return redirect(url_for("super_admin.list_shops"))
    return render_template("super_admin/shop_detail.html", shop=shop)

# =========================================================================
# 4. CREATE SHOP OWNER ACCOUNT
# =========================================================================

@super_admin_bp.route("/shops/create", methods=["GET", "POST"])
@super_admin_required
def create_shop():
    error = None
    if request.method == "POST":
        owner_name = request.form.get("owner_name", "").strip()
        owner_email = request.form.get("owner_email", "").strip().lower()
        initial_password = request.form.get("initial_password", "")
        shop_name = request.form.get("shop_name", "").strip()

        try:
            result = create_shop_owner_and_business(
                admin_id=session["user_id"],
                owner_name=owner_name,
                email=owner_email,
                initial_password=initial_password,
                shop_name=shop_name
            )
            flash(f"Shop Owner '{owner_name}' and shop '{shop_name}' created successfully!", "success")
            return redirect(url_for("super_admin.list_shops"))
        except ValueError as ve:
            error = str(ve)
        except Exception as e:
            error = f"Failed to create shop owner: {str(e)}"

    return render_template("super_admin/create_shop.html", error=error)

# =========================================================================
# 5. ACCESS CONTROL (ENABLE / DISABLE ACCESS)
# =========================================================================

@super_admin_bp.route("/shops/<int:id>/status", methods=["POST"])
@super_admin_required
def set_status(id):
    is_ajax = request.is_json or "application/json" in request.headers.get("Accept", "")
    data = request.get_json(silent=True) if request.is_json else request.form

    new_status = data.get("status", "").strip().lower()
    try:
        result = update_shop_status(business_id=id, new_status=new_status)
        if is_ajax:
            return jsonify(result)
        status_label = "ENABLED" if result["new_status"] == "active" else "DISABLED"
        flash(f"Shop '{result['shop_name']}' access {status_label}.", "success")
        return redirect(request.referrer or url_for("super_admin.list_shops"))
    except Exception as e:
        if is_ajax:
            return jsonify({"success": False, "error": str(e)}), 400
        flash(f"Error updating status: {str(e)}", "error")
        return redirect(request.referrer or url_for("super_admin.list_shops"))

# =========================================================================
# 6. RESET PASSWORD
# =========================================================================

@super_admin_bp.route("/shops/<int:id>/reset-password", methods=["POST"])
@super_admin_required
def reset_password(id):
    is_ajax = request.is_json or "application/json" in request.headers.get("Accept", "")
    data = request.get_json(silent=True) if request.is_json else request.form

    new_password = data.get("new_password", "").strip()

    try:
        result = reset_shop_owner_password(business_id=id, new_password=new_password)
        if is_ajax:
            return jsonify(result)
        flash(f"Password reset for shop '{result['shop_name']}'. Owner must change password on login.", "success")
        return redirect(request.referrer or url_for("super_admin.list_shops"))
    except Exception as e:
        if is_ajax:
            return jsonify({"success": False, "error": str(e)}), 400
        flash(f"Password reset failed: {str(e)}", "error")
        return redirect(request.referrer or url_for("super_admin.list_shops"))

# =========================================================================
# 7. SUPER ADMIN CHANGE OWN PASSWORD
# =========================================================================

@super_admin_bp.route("/change-password", methods=["POST"])
@super_admin_required
def admin_change_password():
    admin_id = session.get("user_id")
    current_password = request.form.get("current_password", "").strip()
    new_password = request.form.get("new_password", "").strip()
    confirm_password = request.form.get("confirm_password", "").strip()

    if not new_password or len(new_password) < 6:
        flash("New password must be at least 6 characters long.", "error")
        return redirect(request.referrer or url_for("super_admin.dashboard"))

    if new_password != confirm_password:
        flash("New password and confirmation do not match.", "error")
        return redirect(request.referrer or url_for("super_admin.dashboard"))

    from models.database import get_db_connection
    from werkzeug.security import check_password_hash, generate_password_hash
    conn = get_db_connection()
    try:
        user_row = conn.execute("SELECT password FROM users WHERE id = ?", (admin_id,)).fetchone()
        if not user_row or not check_password_hash(user_row["password"], current_password):
            flash("Current password is incorrect.", "error")
            return redirect(request.referrer or url_for("super_admin.dashboard"))

        hashed_new = generate_password_hash(new_password)
        conn.execute("UPDATE users SET password = ? WHERE id = ?", (hashed_new, admin_id))
        conn.commit()
        flash("Super Admin password updated successfully.", "success")
        return redirect(request.referrer or url_for("super_admin.dashboard"))
    finally:
        conn.close()
