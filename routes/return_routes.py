from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from services.return_service import search_sale_for_return, process_return, get_returns
from services.business_service import get_business_by_id

return_bp = Blueprint("returns", __name__)

@return_bp.route("/returns")
def index():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    if not biz_id:
        return redirect(url_for("auth.onboarding"))

    returns_list = get_returns(biz_id)
    business = get_business_by_id(biz_id)

    return render_template(
        "returns/list.html",
        returns=returns_list,
        business=business
    )

@return_bp.route("/returns/new", methods=["GET", "POST"])
def new_return():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    business = get_business_by_id(biz_id)
    invoice_number = request.args.get("invoice_number", "").strip()

    sale_data = None
    error = None

    if invoice_number:
        sale_data = search_sale_for_return(biz_id, invoice_number)
        if not sale_data:
            error = f"Invoice '{invoice_number}' not found."

    if request.method == "POST":
        sale_id = int(request.form.get("sale_id"))
        refund_method = request.form.get("refund_method", "cash")
        reason = request.form.get("reason", "").strip()

        # Parse selected items
        items_to_return = []
        product_ids = request.form.getlist("product_id")
        for pid in product_ids:
            qty_val = request.form.get(f"return_qty_{pid}", "0")
            try: qty = float(qty_val)
            except ValueError: qty = 0.0

            if qty > 0:
                restock = request.form.get(f"restock_{pid}") == "1"
                items_to_return.append({
                    "product_id": int(pid) if pid and pid != "None" else None,
                    "product_name": request.form.get(f"product_name_{pid}"),
                    "quantity": qty,
                    "restock": restock
                })

        try:
            return_id = process_return(biz_id, sale_id, items_to_return, refund_method=refund_method, reason=reason)
            return redirect(url_for("returns.index"))
        except Exception as e:
            error = str(e)
            sale_data = search_sale_for_return(biz_id, request.form.get("invoice_number", ""))

    return render_template(
        "returns/new.html",
        business=business,
        sale_data=sale_data,
        invoice_number=invoice_number,
        error=error
    )
