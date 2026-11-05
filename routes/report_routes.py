import csv
import io
from flask import Blueprint, render_template, request, session, redirect, url_for, Response
from services.report_service import get_pnl_report, get_gst_summary
from services.product_service import get_products
from services.business_service import get_business_by_id
from models.database import get_db_connection

report_bp = Blueprint("reports", __name__)

@report_bp.route("/reports")
def index():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    if not biz_id:
        return redirect(url_for("auth.onboarding"))

    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    pnl = get_pnl_report(biz_id, start_date=start_date, end_date=end_date)
    gst = get_gst_summary(biz_id, start_date=start_date, end_date=end_date)
    business = get_business_by_id(biz_id)

    # Inventory Valuation summary
    products = get_products(biz_id, limit=500)
    total_cost_val = sum(p["stock_quantity"] * p["purchase_price"] for p in products)
    total_retail_val = sum(p["stock_quantity"] * p["selling_price"] for p in products)

    return render_template(
        "reports/index.html",
        business=business,
        pnl=pnl,
        gst=gst,
        total_cost_val=round(total_cost_val, 2),
        total_retail_val=round(total_retail_val, 2),
        start_date=start_date,
        end_date=end_date
    )

@report_bp.route("/reports/export/sales/csv")
def export_sales_csv():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    biz_id = session.get("business_id")
    conn = get_db_connection()
    sales = conn.execute("""
    SELECT invoice_number, customer_name, customer_phone, subtotal, discount_amount, tax_amount, 
           grand_total, paid_amount, balance_amount, payment_method, payment_status, created_at
    FROM sales
    WHERE business_id = ?
    ORDER BY created_at DESC
    """, (biz_id,)).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Invoice Number", "Customer Name", "Customer Phone", "Subtotal", "Discount", 
        "Tax (GST)", "Grand Total", "Paid Amount", "Balance", "Payment Method", "Status", "Date Time"
    ])

    for s in sales:
        writer.writerow([
            s["invoice_number"], s["customer_name"], s["customer_phone"], s["subtotal"],
            s["discount_amount"], s["tax_amount"], s["grand_total"], s["paid_amount"],
            s["balance_amount"], s["payment_method"], s["payment_status"], s["created_at"]
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=ShopLedger_Sales_Export.csv"}
    )
