from .auth_routes import auth_bp
from .dashboard_routes import dashboard_bp
from .pos_routes import pos_bp
from .invoice_routes import invoice_bp
from .inventory_routes import inventory_bp
from .customer_routes import customer_bp
from .supplier_routes import supplier_bp
from .expense_routes import expense_bp
from .return_routes import return_bp
from .report_routes import report_bp
from .udhar_routes import udhar_bp
from .super_admin_routes import super_admin_bp

def register_routes(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(pos_bp)
    app.register_blueprint(invoice_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(customer_bp)
    app.register_blueprint(supplier_bp)
    app.register_blueprint(expense_bp)
    app.register_blueprint(return_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(udhar_bp)
    app.register_blueprint(super_admin_bp)
