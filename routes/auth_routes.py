from flask import Blueprint, render_template, request, redirect, session, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from services.auth_service import register_user, authenticate_user, get_user_by_id, update_user_business
from services.business_service import get_business_by_id, get_business_by_owner, create_business, update_business
from models.database import get_db_connection

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        if session.get("user_role") == "SUPER_ADMIN":
            return redirect(url_for("super_admin.dashboard"))
        if session.get("business_id"):
            return redirect(url_for("dashboard.index"))

    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = authenticate_user(email, password)
        if user:
            # Check if Super Admin logging in through normal form
            if user.get("role") == "SUPER_ADMIN":
                session["user_id"] = user["id"]
                session["user_email"] = user["email"]
                session["user_name"] = user["name"] or "Super Administrator"
                session["user_role"] = "SUPER_ADMIN"
                session["session_version"] = user.get("session_version", 1)
                return redirect(url_for("super_admin.dashboard"))

            # Check if user account is disabled
            if user.get("account_status") in ("disabled", "suspended", "deactivated"):
                error = "Your shop account has been disabled. Access denied."
                return render_template("auth/login.html", error=error)

            session["user_id"] = user["id"]
            session["user_email"] = user["email"]
            session["user_name"] = user["name"] or user["email"].split("@")[0].capitalize()
            session["user_role"] = user.get("role", "SHOP_OWNER")
            session["session_version"] = user.get("session_version", 1)

            # Check if user has an existing business
            biz = get_business_by_id(user.get("business_id"))
            if not biz:
                biz = get_business_by_owner(user["id"])

            if biz:
                if biz.get("status") in ("disabled", "suspended", "deactivated"):
                    session.clear()
                    error = "Your shop account has been disabled. Access denied."
                    return render_template("auth/login.html", error=error)

                session["business_id"] = biz["id"]
                session["business_name"] = biz["name"]
                update_user_business(user["id"], biz["id"])

                # Check if first login requires password change
                if user.get("must_change_password") == 1:
                    session["must_change_password"] = True
                    return redirect(url_for("auth.first_login_password"))

                return redirect(url_for("dashboard.index"))
            else:
                if user.get("must_change_password") == 1:
                    session["must_change_password"] = True
                    return redirect(url_for("auth.first_login_password"))
                return redirect(url_for("auth.onboarding"))
        else:
            error = "Invalid email or password. Please check your credentials."

    return render_template("auth/login.html", error=error)

@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    """
    Public account self-registration is disabled for commercial security.
    Preserves existing user accounts and prevents unauthorized public registration.
    """
    if request.method == "POST":
        if request.is_json:
            return {"success": False, "error": "Public registration is disabled. Please contact your system administrator."}, 403
        flash("Public account registration is disabled. Please contact your system administrator to obtain login credentials.", "error")
        return render_template("auth/login.html", error="Public account registration is disabled. Please contact your system administrator."), 403

    flash("Public account registration is disabled. Please sign in with your authorized shop credentials.", "warning")
    return redirect(url_for("auth.login"))

@auth_bp.route("/onboarding", methods=["GET", "POST"])
def onboarding():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    error = None
    if request.method == "POST":
        name = request.form.get("business_name", "").strip()
        category = request.form.get("category", "kirana").strip().lower()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        gstin = request.form.get("gstin", "").strip().upper()
        currency = request.form.get("currency", "₹").strip()
        invoice_prefix = request.form.get("invoice_prefix", "INV-").strip() or "INV-"
        tax_enabled = 1 if request.form.get("tax_enabled") == "1" else 0
        default_tax_rate = float(request.form.get("default_tax_rate", 0.0) or 0.0)

        if not name:
            error = "Please enter your store or shop name."
            return render_template("auth/onboarding.html", error=error)

        try:
            biz_id = create_business(
                owner_id=session["user_id"],
                name=name,
                category=category,
                phone=phone,
                email=session["user_email"],
                address=address,
                gstin=gstin,
                currency=currency,
                invoice_prefix=invoice_prefix,
                tax_enabled=tax_enabled,
                default_tax_rate=default_tax_rate
            )
            session["business_id"] = biz_id
            session["business_name"] = name
            return redirect(url_for("dashboard.index"))
        except Exception as e:
            error = f"Error creating shop profile: {str(e)}"

    return render_template("auth/onboarding.html", error=error)

@auth_bp.route("/settings", methods=["GET", "POST"])
def settings():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    biz = get_business_by_id(biz_id)
    if not biz:
        return redirect(url_for("auth.onboarding"))

    success = False
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "retail").strip().lower()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        address = request.form.get("address", "").strip()
        gstin = request.form.get("gstin", "").strip().upper()
        currency = request.form.get("currency", "₹").strip() or "₹"
        invoice_prefix = request.form.get("invoice_prefix", "INV-").strip() or "INV-"
        tax_enabled = 1 if request.form.get("tax_enabled") == "1" else 0
        default_tax_rate = float(request.form.get("default_tax_rate", 0.0) or 0.0)
        terms = request.form.get("terms_conditions", "").strip()

        update_business(
            business_id=biz_id,
            name=name,
            category=category,
            phone=phone,
            email=email,
            address=address,
            gstin=gstin,
            currency=currency,
            invoice_prefix=invoice_prefix,
            tax_enabled=tax_enabled,
            default_tax_rate=default_tax_rate,
            terms_conditions=terms
        )
        session["business_name"] = name
        biz = get_business_by_id(biz_id)
        success = True

    return render_template("settings/index.html", business=biz, success=success)

@auth_bp.route("/change-password", methods=["POST"])
def change_password():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    user_id = session["user_id"]
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    biz_id = session.get("business_id")
    biz = get_business_by_id(biz_id)

    if not new_password or len(new_password) < 6:
        return render_template("settings/index.html", business=biz, success=False, pw_error="New password must be at least 6 characters long.")

    if new_password != confirm_password:
        return render_template("settings/index.html", business=biz, success=False, pw_error="New password and confirmation do not match.")

    conn = get_db_connection()
    user_row = conn.execute("SELECT password FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user_row:
        conn.close()
        return redirect(url_for("auth.login"))

    from werkzeug.security import check_password_hash, generate_password_hash
    if not check_password_hash(user_row["password"], current_password):
        conn.close()
        return render_template("settings/index.html", business=biz, success=False, pw_error="Current password is incorrect.")

    hashed_new = generate_password_hash(new_password)
    conn.execute("UPDATE users SET password = ?, session_version = session_version + 1 WHERE id = ?", (hashed_new, user_id))
    conn.commit()
    conn.close()

    # Keep session alive but update version
    session["session_version"] = session.get("session_version", 1) + 1
    return render_template("settings/index.html", business=biz, success=False, pw_success=True)

@auth_bp.route("/first-login-password", methods=["GET", "POST"])
def first_login_password():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    user_id = session["user_id"]
    error = None
    if request.method == "POST":
        new_password = request.form.get("new_password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if not new_password or len(new_password) < 6:
            error = "Password must be at least 6 characters long."
        elif new_password != confirm_password:
            error = "Passwords do not match."
        else:
            conn = get_db_connection()
            hashed = generate_password_hash(new_password)
            conn.execute("UPDATE users SET password = ?, must_change_password = 0, session_version = session_version + 1 WHERE id = ?", (hashed, user_id))
            conn.commit()
            conn.close()

            session.pop("must_change_password", None)
            session["session_version"] = session.get("session_version", 1) + 1
            flash("Your personal password has been set. Welcome to your shop management portal!", "success")
            return redirect(url_for("dashboard.index"))

    return render_template("auth/first_login_password.html", error=error)

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
