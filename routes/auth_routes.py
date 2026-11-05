from flask import Blueprint, render_template, request, redirect, session, url_for, flash
from services.auth_service import register_user, authenticate_user, get_user_by_id, update_user_business
from services.business_service import get_business_by_id, get_business_by_owner, create_business, update_business

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session and session.get("business_id"):
        return redirect(url_for("dashboard.index"))

    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = authenticate_user(email, password)
        if user:
            session["user_id"] = user["id"]
            session["user_email"] = user["email"]
            session["user_name"] = user["name"] or user["email"].split("@")[0].capitalize()
            session["user_role"] = user.get("role", "owner")

            # Check if user has an existing business
            biz = get_business_by_id(user.get("business_id"))
            if not biz:
                biz = get_business_by_owner(user["id"])

            if biz:
                session["business_id"] = biz["id"]
                session["business_name"] = biz["name"]
                update_user_business(user["id"], biz["id"])
                return redirect(url_for("dashboard.index"))
            else:
                return redirect(url_for("auth.onboarding"))
        else:
            error = "Invalid email or password. Please check your credentials."

    return render_template("auth/login.html", error=error)

@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if "user_id" in session and session.get("business_id"):
        return redirect(url_for("dashboard.index"))

    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        name = request.form.get("name", "").strip()

        if not email or not password:
            error = "Email and password are required."
            return render_template("auth/signup.html", error=error)

        try:
            user_id = register_user(email, password, name=name, role="owner")
            session["user_id"] = user_id
            session["user_email"] = email
            session["user_name"] = name or email.split("@")[0].capitalize()
            session["user_role"] = "owner"
            return redirect(url_for("auth.onboarding"))
        except Exception:
            error = "An account with this email already exists."

    return render_template("auth/signup.html", error=error)

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

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
