import datetime
from werkzeug.security import generate_password_hash
from models.database import get_db_connection

def get_simple_metrics():
    """Returns core platform numbers: Total Shops, Active Shops, Disabled Shops."""
    conn = get_db_connection()
    try:
        # Total Registered Shops
        row = conn.execute("SELECT COUNT(*) FROM businesses").fetchone()
        total_shops = int(row[0]) if row else 0

        # Active Shops
        row = conn.execute("""
        SELECT COUNT(b.id) 
        FROM businesses b
        JOIN users u ON b.owner_id = u.id
        WHERE (b.status = 'active' OR b.status IS NULL) 
          AND (u.account_status = 'active' OR u.account_status IS NULL)
        """).fetchone()
        active_shops = int(row[0]) if row else 0

        # Disabled Shops
        row = conn.execute("""
        SELECT COUNT(b.id) 
        FROM businesses b
        JOIN users u ON b.owner_id = u.id
        WHERE b.status = 'disabled' OR u.account_status = 'disabled'
        """).fetchone()
        disabled_shops = int(row[0]) if row else 0

        return {
            "total_shops": total_shops,
            "active_shops": active_shops,
            "disabled_shops": disabled_shops
        }
    finally:
        conn.close()

def get_all_shops(search=None):
    """
    Returns registered shops list.
    Columns: Shop Owner Name, Shop Name, Email Address, Account Creation Date, Access Status, Actions.
    """
    conn = get_db_connection()
    try:
        query = """
        SELECT b.id, b.name as shop_name, b.status as shop_status, b.created_at as created_at,
               u.id as owner_id, u.name as owner_name, u.email as owner_email,
               COALESCE(u.account_status, 'active') as account_status,
               u.must_change_password
        FROM businesses b
        JOIN users u ON b.owner_id = u.id
        WHERE 1=1
        """
        params = []
        if search:
            s = f"%{search.strip().lower()}%"
            query += " AND (LOWER(b.name) LIKE ? OR LOWER(u.name) LIKE ? OR LOWER(u.email) LIKE ?)"
            params.extend([s, s, s])

        query += " ORDER BY b.created_at DESC"
        rows = conn.execute(query, params).fetchall()

        shops = []
        for r in rows:
            d = dict(r)
            # Determine effective access status: 'active' or 'disabled'
            is_disabled = (d.get("shop_status") == "disabled" or d.get("account_status") == "disabled")
            d["access_status"] = "disabled" if is_disabled else "active"
            shops.append(d)

        return shops
    finally:
        conn.close()

def get_shop_details(business_id):
    """Returns single shop information."""
    conn = get_db_connection()
    try:
        shop = conn.execute("""
        SELECT b.id, b.name as shop_name, b.category, b.phone as shop_phone, b.email as shop_email,
               b.address, b.gstin, b.status as shop_status, b.created_at,
               u.id as owner_id, u.name as owner_name, u.email as owner_email,
               COALESCE(u.account_status, 'active') as account_status,
               u.must_change_password, u.session_version
        FROM businesses b
        JOIN users u ON b.owner_id = u.id
        WHERE b.id = ?
        """, (business_id,)).fetchone()

        if not shop:
            return None

        d = dict(shop)
        is_disabled = (d.get("shop_status") == "disabled" or d.get("account_status") == "disabled")
        d["access_status"] = "disabled" if is_disabled else "active"
        return d
    finally:
        conn.close()

def create_shop_owner_and_business(admin_id, owner_name, email, initial_password, shop_name):
    """
    Creates a new shop owner account and associated shop:
    - Creates shop owner user with initial password securely hashed.
    - Assigns role = 'SHOP_OWNER'.
    - Sets must_change_password = 1 so owner must change it on first login.
    - Sets account_status = 'active'.
    - Creates business and links user.
    - Validates uniqueness of email.
    """
    owner_name = (owner_name or "").strip()
    email_clean = (email or "").strip().lower()
    shop_name = (shop_name or "").strip()
    initial_password = (initial_password or "").strip()

    if not owner_name:
        raise ValueError("Shop Owner Name is required.")
    if not email_clean or "@" not in email_clean:
        raise ValueError("A valid email address is required.")
    if not initial_password or len(initial_password) < 6:
        raise ValueError("Initial Password must be at least 6 characters long.")
    if not shop_name:
        raise ValueError("Shop Name is required.")

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # Prevent duplicate emails
        existing = cur.execute("SELECT id FROM users WHERE LOWER(email) = ?", (email_clean,)).fetchone()
        if existing:
            raise ValueError(f"An account with email '{email_clean}' is already registered.")

        # Hash initial password securely
        hashed_password = generate_password_hash(initial_password)

        # Create shop owner user
        cur.execute("""
        INSERT INTO users (email, password, name, role, account_status, must_change_password, session_version)
        VALUES (?, ?, ?, 'SHOP_OWNER', 'active', 1, 1)
        """, (email_clean, hashed_password, owner_name))
        user_id = cur.lastrowid

        # Create business entry
        cur.execute("""
        INSERT INTO businesses (owner_id, name, status)
        VALUES (?, ?, 'active')
        """, (user_id, shop_name))
        business_id = cur.lastrowid

        # Associate shop owner with business
        cur.execute("UPDATE users SET business_id = ? WHERE id = ?", (business_id, user_id))

        conn.commit()
        return {
            "success": True,
            "business_id": business_id,
            "user_id": user_id,
            "shop_name": shop_name,
            "owner_email": email_clean
        }
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def update_shop_status(business_id, new_status):
    """
    Enables or disables shop access:
    - If disabled: bumps session_version to immediately revoke existing login sessions.
    - If enabled: sets account_status and business status back to 'active'.
    """
    clean_status = "disabled" if new_status.lower() in ["disabled", "suspend", "suspended"] else "active"

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        biz = cur.execute("SELECT id, name, owner_id FROM businesses WHERE id = ?", (business_id,)).fetchone()
        if not biz:
            raise ValueError(f"Shop #{business_id} not found.")

        # Update business status
        cur.execute("UPDATE businesses SET status = ? WHERE id = ?", (clean_status, business_id))

        # Update user account_status and bump session_version to invalidate live sessions
        cur.execute("""
        UPDATE users 
        SET account_status = ?, 
            session_version = session_version + 1 
        WHERE id = ?
        """, (clean_status, biz["owner_id"]))

        conn.commit()
        return {
            "success": True,
            "business_id": business_id,
            "shop_name": biz["name"],
            "new_status": clean_status
        }
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def reset_shop_owner_password(business_id, new_password):
    """
    Sets a new password for the shop owner:
    - Hashes password securely.
    - Flags must_change_password = 1.
    - Bumps session_version to revoke any old sessions.
    """
    if not new_password or len(new_password) < 6:
        raise ValueError("Password must be at least 6 characters long.")

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        biz = cur.execute("SELECT id, name, owner_id FROM businesses WHERE id = ?", (business_id,)).fetchone()
        if not biz:
            raise ValueError(f"Shop #{business_id} not found.")

        hashed = generate_password_hash(new_password)
        cur.execute("""
        UPDATE users 
        SET password = ?, 
            must_change_password = 1,
            session_version = session_version + 1 
        WHERE id = ?
        """, (hashed, biz["owner_id"]))

        conn.commit()
        return {
            "success": True,
            "business_id": business_id,
            "shop_name": biz["name"]
        }
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
