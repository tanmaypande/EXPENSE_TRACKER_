import datetime
from models.database import get_db_connection

def get_dashboard_metrics(business_id):
    """
    Computes all high-priority business metrics from real database records:
    1. Today's sales, today's profit, today's expenses
    2. Total inventory value, low-stock count
    3. Customer pending credit/receivables
    4. 7-day sales graph data & top selling items
    """
    conn = get_db_connection()
    today_str = datetime.date.today().strftime("%Y-%m-%d")

    # 1. Today's Sales & COGS
    row_today = conn.execute("""
    SELECT 
        COALESCE(SUM(s.grand_total), 0.0) as today_sales,
        COALESCE(SUM(s.tax_amount), 0.0) as today_tax,
        COALESCE((
            SELECT SUM(si.purchase_price * si.quantity)
            FROM sale_items si
            JOIN sales s2 ON si.sale_id = s2.id
            WHERE s2.business_id = ? AND date(s2.created_at) = date('now', 'localtime')
        ), 0.0) as today_cogs,
        COUNT(s.id) as today_tx_count
    FROM sales s
    WHERE s.business_id = ? AND date(s.created_at) = date('now', 'localtime')
    """, (business_id, business_id)).fetchone()

    today_sales = float(row_today["today_sales"])
    today_cogs = float(row_today["today_cogs"])
    today_tx_count = int(row_today["today_tx_count"])

    # 2. Today's Expenses
    row_exp = conn.execute("""
    SELECT COALESCE(SUM(amount), 0.0) as today_expense
    FROM expenses
    WHERE business_id = ? AND date = date('now', 'localtime')
    """, (business_id,)).fetchone()
    today_expense = float(row_exp["today_expense"])

    # Profit calculations
    # Gross Profit = Sales Revenue (net of tax) - Cost of Goods Sold
    today_tax = float(row_today["today_tax"])
    today_net_revenue = max(0.0, today_sales - today_tax)
    today_gross_profit = max(0.0, today_net_revenue - today_cogs)
    today_net_profit = today_gross_profit - today_expense

    # 3. Overall Inventory metrics
    row_inv = conn.execute("""
    SELECT 
        COUNT(id) as total_products,
        COALESCE(SUM(stock_quantity * purchase_price), 0.0) as total_inventory_cost,
        COALESCE(SUM(stock_quantity * selling_price), 0.0) as total_inventory_retail,
        COALESCE(SUM(CASE WHEN stock_quantity <= min_stock_level THEN 1 ELSE 0 END), 0) as low_stock_count
    FROM products
    WHERE business_id = ? AND is_active = 1
    """, (business_id,)).fetchone()

    total_products = int(row_inv["total_products"])
    total_inventory_cost = float(row_inv["total_inventory_cost"])
    total_inventory_retail = float(row_inv["total_inventory_retail"])
    low_stock_count = int(row_inv["low_stock_count"])

    # 4. Total customer outstanding credit (Receivables / Udhar)
    row_cust = conn.execute("""
    SELECT COALESCE(SUM(outstanding_balance), 0.0) as total_receivable
    FROM customers
    WHERE business_id = ?
    """, (business_id,)).fetchone()
    total_receivable = float(row_cust["total_receivable"])

    # 5. Last 7 Days Daily Sales Trend (Real Data)
    rows_trend = conn.execute("""
    SELECT 
        date(created_at) as sale_date,
        COALESCE(SUM(grand_total), 0.0) as daily_revenue
    FROM sales
    WHERE business_id = ? AND date(created_at) >= date('now', '-6 days', 'localtime')
    GROUP BY date(created_at)
    ORDER BY date(created_at) ASC
    """, (business_id,)).fetchall()

    trend_dict = {r["sale_date"]: float(r["daily_revenue"]) for r in rows_trend}
    labels_7d = []
    values_7d = []
    for i in range(6, -1, -1):
        d = (datetime.date.today() - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        labels_7d.append(datetime.datetime.strptime(d, "%Y-%m-%d").strftime("%b %d"))
        values_7d.append(trend_dict.get(d, 0.0))

    # 6. Top Selling Products
    rows_top = conn.execute("""
    SELECT si.product_name, SUM(si.quantity) as total_qty, SUM(si.total_amount) as total_revenue
    FROM sale_items si
    JOIN sales s ON si.sale_id = s.id
    WHERE s.business_id = ?
    GROUP BY si.product_name
    ORDER BY total_qty DESC
    LIMIT 5
    """, (business_id,)).fetchall()

    top_products = [dict(r) for r in rows_top]

    # 7. Recent Invoices
    rows_recent = conn.execute("""
    SELECT s.id, s.invoice_number, s.customer_name, s.grand_total, s.payment_method, s.payment_status, s.created_at
    FROM sales s
    WHERE s.business_id = ?
    ORDER BY s.created_at DESC
    LIMIT 6
    """, (business_id,)).fetchall()

    conn.close()

    return {
        "today_sales": today_sales,
        "today_expense": today_expense,
        "today_gross_profit": round(today_gross_profit, 2),
        "today_net_profit": round(today_net_profit, 2),
        "today_tx_count": today_tx_count,
        "total_products": total_products,
        "total_inventory_cost": round(total_inventory_cost, 2),
        "total_inventory_retail": round(total_inventory_retail, 2),
        "low_stock_count": low_stock_count,
        "total_receivable": round(total_receivable, 2),
        "sales_labels_7d": labels_7d,
        "sales_values_7d": values_7d,
        "top_products": top_products,
        "recent_invoices": [dict(r) for r in rows_recent]
    }

def get_pnl_report(business_id, start_date=None, end_date=None):
    """
    Comprehensive Commercial Profit & Loss Statement:
    Revenue - Tax - COGS = Gross Profit
    Gross Profit - Operating Expenses = Net Profit
    """
    conn = get_db_connection()
    query_sales = """
    SELECT 
        COALESCE(SUM(grand_total), 0.0) as gross_sales,
        COALESCE(SUM(discount_amount), 0.0) as total_discounts,
        COALESCE(SUM(tax_amount), 0.0) as total_tax,
        COALESCE((
            SELECT SUM(si.purchase_price * si.quantity)
            FROM sale_items si
            JOIN sales s2 ON si.sale_id = s2.id
            WHERE s2.business_id = ?
            {date_filter_s2}
        ), 0.0) as total_cogs
    FROM sales
    WHERE business_id = ?
    """
    sub_params = [business_id]
    date_filter_s2 = ""
    if start_date:
        date_filter_s2 += " AND date(s2.created_at) >= ?"
        sub_params.append(start_date)
    if end_date:
        date_filter_s2 += " AND date(s2.created_at) <= ?"
        sub_params.append(end_date)

    main_params = [business_id]
    date_filter = ""
    if start_date:
        date_filter += " AND date(created_at) >= ?"
        main_params.append(start_date)
    if end_date:
        date_filter += " AND date(created_at) <= ?"
        main_params.append(end_date)

    query_sales = query_sales.format(date_filter_s2=date_filter_s2) + date_filter
    all_params = sub_params + main_params

    row_sales = conn.execute(query_sales, all_params).fetchone()
    gross_sales = float(row_sales["gross_sales"])
    total_tax = float(row_sales["total_tax"])
    total_cogs = float(row_sales["total_cogs"])

    # Net revenue excluding taxes
    net_sales = max(0.0, round(gross_sales - total_tax, 2))
    gross_profit = max(0.0, round(net_sales - total_cogs, 2))
    gross_margin_pct = round((gross_profit / net_sales) * 100, 1) if net_sales > 0 else 0.0

    # Total Operating Expenses
    query_exp = "SELECT COALESCE(SUM(amount), 0.0) as total_expenses FROM expenses WHERE business_id = ?"
    params_exp = [business_id]
    if start_date:
        query_exp += " AND date >= ?"
        params_exp.append(start_date)
    if end_date:
        query_exp += " AND date <= ?"
        params_exp.append(end_date)

    row_exp = conn.execute(query_exp, params_exp).fetchone()
    operating_expenses = float(row_exp["total_expenses"])
    net_profit = round(gross_profit - operating_expenses, 2)
    net_margin_pct = round((net_profit / net_sales) * 100, 1) if net_sales > 0 else 0.0

    # Expenses breakdown by category
    query_exp_cats = """
    SELECT category, COALESCE(SUM(amount), 0.0) as cat_total
    FROM expenses
    WHERE business_id = ?
    """
    params_exp_cats = [business_id]
    if start_date:
        query_exp_cats += " AND date >= ?"
        params_exp_cats.append(start_date)
    if end_date:
        query_exp_cats += " AND date <= ?"
        params_exp_cats.append(end_date)
    query_exp_cats += " GROUP BY category ORDER BY cat_total DESC"

    exp_cats = conn.execute(query_exp_cats, params_exp_cats).fetchall()

    conn.close()

    return {
        "gross_sales": gross_sales,
        "total_tax": total_tax,
        "tax_collected": total_tax,
        "net_sales": net_sales,
        "operating_revenue": net_sales,
        "returns_total": 0.0,
        "cogs": total_cogs,
        "gross_profit": gross_profit,
        "gross_margin_pct": gross_margin_pct,
        "operating_expenses": operating_expenses,
        "total_expenses": operating_expenses,
        "net_profit": net_profit,
        "net_margin_pct": net_margin_pct,
        "total_invoices": len(exp_cats),
        "expense_categories": [dict(c) for c in exp_cats]
    }

def get_gst_summary(business_id, start_date=None, end_date=None):
    """Computes Indian GST turnover and tax liabilities."""
    conn = get_db_connection()
    query = """
    SELECT 
        COALESCE(SUM(subtotal - discount_amount), 0.0) as taxable_turnover,
        COALESCE(SUM(cgst_amount), 0.0) as total_cgst,
        COALESCE(SUM(sgst_amount), 0.0) as total_sgst,
        COALESCE(SUM(tax_amount), 0.0) as total_gst,
        COALESCE(SUM(grand_total), 0.0) as gross_turnover,
        COUNT(id) as total_b2c_invoices
    FROM sales
    WHERE business_id = ?
    """
    params = [business_id]
    if start_date:
        query += " AND date(created_at) >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date(created_at) <= ?"
        params.append(end_date)

    row = conn.execute(query, params).fetchone()
    conn.close()
    d = dict(row)
    d["cgst"] = d.get("total_cgst", 0.0)
    d["sgst"] = d.get("total_sgst", 0.0)
    d["total_tax"] = d.get("total_gst", 0.0)
    return d

def get_monthly_trends(business_id, months=6):
    """Computes monthly financial trends for the last N months."""
    conn = get_db_connection()
    today = datetime.date.today()
    labels = []
    sales_data = []
    expenses_data = []
    profit_data = []

    month_tuples = []
    for i in range(months - 1, -1, -1):
        year = today.year
        month = today.month - i
        while month <= 0:
            month += 12
            year -= 1
        month_tuples.append((year, month))

    for year, month in month_tuples:
        ym_str = f"{year:04d}-{month:02d}"
        label = datetime.date(year, month, 1).strftime("%b %Y")
        labels.append(label)

        s_row = conn.execute("""
        SELECT COALESCE(SUM(grand_total), 0.0) as s_total
        FROM sales
        WHERE business_id = ? AND strftime('%Y-%m', created_at) = ?
        """, (business_id, ym_str)).fetchone()
        s_val = float(s_row["s_total"]) if s_row else 0.0
        sales_data.append(round(s_val, 2))

        e_row = conn.execute("""
        SELECT COALESCE(SUM(amount), 0.0) as e_total
        FROM expenses
        WHERE business_id = ? AND strftime('%Y-%m', date) = ?
        """, (business_id, ym_str)).fetchone()
        e_val = float(e_row["e_total"]) if e_row else 0.0
        expenses_data.append(round(e_val, 2))

        profit_data.append(round(s_val - e_val, 2))

    conn.close()
    return {
        "labels": labels,
        "sales": sales_data,
        "expenses": expenses_data,
        "profit": profit_data
    }

def get_receivables_and_payables(business_id):
    """Fetches total outstanding customer receivables and supplier payables."""
    conn = get_db_connection()
    r_row = conn.execute("""
    SELECT COALESCE(SUM(outstanding_balance), 0.0) as total_receivable
    FROM customers
    WHERE business_id = ? AND outstanding_balance > 0
    """, (business_id,)).fetchone()
    total_receivable = float(r_row["total_receivable"]) if r_row else 0.0

    p_row = conn.execute("""
    SELECT COALESCE(SUM(outstanding_balance), 0.0) as total_payable
    FROM suppliers
    WHERE business_id = ? AND outstanding_balance > 0
    """, (business_id,)).fetchone()
    total_payable = float(p_row["total_payable"]) if p_row else 0.0

    conn.close()
    return {
        "total_receivable": round(total_receivable, 2),
        "total_payable": round(total_payable, 2)
    }
