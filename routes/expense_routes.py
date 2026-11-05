import datetime
from flask import Blueprint, render_template, request, session, redirect, url_for
from services.expense_service import get_expenses, create_expense, delete_expense, get_expense_categories
from services.business_service import get_business_by_id

expense_bp = Blueprint("expenses", __name__)

@expense_bp.route("/expenses")
def index():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    if not biz_id:
        return redirect(url_for("auth.onboarding"))

    category = request.args.get("category")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    expenses = get_expenses(biz_id, category=category, start_date=start_date, end_date=end_date)
    categories = get_expense_categories()
    business = get_business_by_id(biz_id)
    total_amount = sum(e["amount"] for e in expenses)

    return render_template(
        "expenses/list.html",
        expenses=expenses,
        categories=categories,
        business=business,
        selected_category=category,
        total_amount=total_amount,
        today=datetime.date.today().strftime("%Y-%m-%d")
    )

@expense_bp.route("/expenses/add", methods=["POST"])
def add():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    category = request.form.get("category", "Miscellaneous").strip()
    amount = float(request.form.get("amount", 0.0) or 0.0)
    date = request.form.get("date") or datetime.date.today().strftime("%Y-%m-%d")
    desc = request.form.get("description", "").strip()
    method = request.form.get("payment_method", "cash")

    create_expense(biz_id, category=category, amount=amount, date=date, description=desc, payment_method=method)
    return redirect(url_for("expenses.index"))

@expense_bp.route("/expenses/delete/<int:id>", methods=["GET", "POST"])
def remove(id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    delete_expense(id, biz_id)
    return redirect(url_for("expenses.index"))

# Backward-compatible legacy endpoints (/add and /delete/<id>)
@expense_bp.route("/add", methods=["GET", "POST"])
def legacy_add():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        biz_id = session.get("business_id")
        cat = request.form.get("category", "General").strip()
        amt = float(request.form.get("amount", 0.0) or 0.0)
        dt = request.form.get("date") or datetime.date.today().strftime("%Y-%m-%d")
        desc = request.form.get("description", "").strip()
        method = request.form.get("payment_method", "cash")
        if biz_id:
            create_expense(biz_id, category=cat, amount=amt, date=dt, description=desc, payment_method=method)
        return redirect(url_for("dashboard.index"))

    return redirect(url_for("expenses.index"))

@expense_bp.route("/delete/<int:id>", methods=["GET", "POST"])
def legacy_delete(id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
    biz_id = session.get("business_id")
    if biz_id:
        delete_expense(id, biz_id)
    return redirect(url_for("dashboard.index"))
