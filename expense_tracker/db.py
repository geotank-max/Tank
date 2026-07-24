import os
from pathlib import Path

import oracledb
from dotenv import load_dotenv
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

CATEGORIES = [
    'Food', 'Transport', 'Shopping', 'Housing',
    'Healthcare', 'Entertainment', 'Education', 'Other'
]

CAT_COLORS = [
    '#FF6B6B', '#4D96FF', '#6BCB77', '#FFD93D', 
    '#9B5DE5', '#F15BB5', '#00BBF9', '#00F5D4',
    '#FF9F1C', '#2EC4B6', '#E71D36', '#FF9F1C'
]

def add_new_category(category_name):
    """Inserts a new category into the database with a pre-calculated color assignment."""
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Count existing entries to pick the next color in line sequentially
            cur.execute("SELECT COUNT(*) FROM categories")
            count = cur.fetchone()[0]
            
            # 2. Use modulo operator (%) to prevent OutOfIndex bounds crashes
            assigned_color = CAT_COLORS[count % len(CAT_COLORS)]
            
            # 3. Save the new category row (Make sure your schema has a color column)
            sql = """
                INSERT INTO categories (category_name, category_color) 
                VALUES (:name, :color)
            """
            cur.execute(sql, {'name': category_name.strip(), 'color': assigned_color})
        conn.commit()

def get_connection():
    return oracledb.connect(
        user=os.getenv("ORACLE_USER"),
        password=os.getenv("ORACLE_PASSWORD"),
        host=os.getenv("ORACLE_HOST"),
        port=os.getenv("ORACLE_PORT"),
        sid=os.getenv("ORACLE_SID")
    )

def get_category_expense_df():
    sql = """
        SELECT 
            c.category_name AS category,
            SUM(e.amount) AS amount
        FROM expenses e
        JOIN categories c
            ON e.category_id = c.category_id
        GROUP BY c.category_name
        ORDER BY c.category_name          
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            cols = [d[0].lower() for d in cur.description]
            rows = cur.fetchall()
            return pd.DataFrame(rows, columns=cols)
        
def get_monthly_expense_df():
    sql = """
        SELECT
            TO_CHAR(expense_date,'YYYY-MM'),
            SUM(amount)
        FROM expenses
        GROUP BY TO_CHAR(expense_date,'YYYY-MM')
        ORDER BY TO_CHAR(expense_date,'YYYY-MM')
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            cols = [d[0].lower() for d in cur.description]
            rows = cur.fetchall()
            return pd.DataFrame(rows, columns=cols)
        
def get_category_chart_df():
    sql = """
        SELECT
            c.category_name AS category,
            SUM(e.amount) AS amount
        FROM expenses e
        JOIN categories c
            ON e.category_id = c.category_id
        GROUP BY c.category_name
        ORDER BY SUM(e.amount) DESC        
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            cols = [d[0].lower() for d in cur.description]
            rows = cur.fetchall()
            return pd.DataFrame(rows, columns=cols)


def get_all_expenses(user_id):
    sql = """
        SELECT
            e.expense_id AS expense_id,
            c.category_name AS category_name,
            c.category_color AS category_color,
            e.amount AS amount,
            e.description AS description,
            TO_CHAR(e.expense_date, 'DD Mon YYYY') AS expense_date
        FROM expenses e
        JOIN categories c ON e.category_id = c.category_id
        WHERE e.user_id = :user_id
        ORDER BY e.expense_id DESC
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {'user_id': user_id})
            
            # FORCE LOWERCASE COLUMN STRINGS HERE:
            cols = [d[0].lower() for d in cur.description] 
            
            return [dict(zip(cols, row)) for row in cur.fetchall()]

def get_recent_expenses(user_id):
    """Fetch only the 5 most recent expenses for the user's dashboard view."""
    sql = """
        SELECT
            e.expense_id AS expense_id,
            c.category_name AS category_name,
            c.category_color AS category_color,  -- ADDED HERE
            e.amount AS amount,
            e.description AS description,
            TO_CHAR(e.expense_date, 'DD Mon YYYY') AS expense_date
        FROM expenses e
        LEFT JOIN categories c ON e.category_id = c.category_id
        WHERE e.user_id = :user_id
        ORDER BY e.expense_date DESC, e.expense_id DESC
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {'user_id': user_id})
            cols = [d[0].lower() for d in cur.description] 
            return [dict(zip(cols, row)) for row in cur.fetchmany(5)] #
        
        
def get_filterd_expenses(user_id, category: str ='', search: str = '', sort: str = 'date_desc'):
    """Filter expenses belonging ONLY to the logged-in user"""
    sort_map = {
        'date_desc': 'e.expense_date DESC, e.expense_id DESC',
        'date_asc': 'e.expense_date ASC, e.expense_id ASC',
        'amount_desc': 'e.amount DESC',
        'amount_asc': 'e.amount ASC',
    }
    order = sort_map.get(sort,'e.expense_date DESC, e.expense_id DESC')

    #Force checking user_id safety constraint
    conditions = ['e.user_id = :user_id']
    params = {'user_id': user_id}

    if category:
        conditions.append('c.category_name = :category')
        params['category'] = category

    if search:
        conditions.append('LOWER(e.description) LIKE :search')
        params['search'] = f'%{search.lower()}%'

    sql = f"""
        SELECT e.expense_id, 
               c.category_name,
               e.amount, 
               TO_CHAR(e.expense_date, 'YYYY-MM-DD') AS expense_date,
               e.description
        FROM expenses e
        JOIN categories c 
        ON e.category_id = c.category_id
        WHERE {' AND '.join(conditions)}
        ORDER BY {order}
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d[0].lower() for d in cur.description]
            rows = cur.fetchall()
            return pd.DataFrame(rows, columns=cols)
        
def add_expense(user_id,category_name: str, amount: float, date: str, description: str):
    """Insert a new expense row by mapping category name to ID."""
    
    # FIX: Subquery looks up category_id matching the provided text name string
    sql = """
        INSERT INTO expenses (user_id, category_id, amount, expense_date, description)
        VALUES (
            :user_id, 
            (SELECT category_id FROM categories WHERE category_name = :category_name), 
            :amount, 
            TO_DATE(:expense_date, 'YYYY-MM-DD'), 
            :description
        )
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {
                'user_id': user_id,
                'category_name': category_name, 
                'amount': amount, 
                'expense_date': date, 
                'description': description
            })
        conn.commit()

def get_expense_by_id(expense_id):
    sql = """
        SELECT e.expense_id, c.category_name, e.amount, 
               TO_CHAR(e.expense_date, 'YYYY-MM-DD') AS expense_date, 
               e.description
        FROM expenses e
        JOIN categories c ON e.category_id = c.category_id
        WHERE e.expense_id = :expense_id
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {'expense_id': expense_id})
            row = cur.fetchone()
            if row:
                # FORCE LOWERCASE KEYS HERE:
                cols = [d[0].lower() for d in cur.description]
                return dict(zip(cols, row))
    return None
        
def update_expense(expense_id: int, amount: float,
                   category_name: str, date: str, description: str):
    """Update every editable field of an expense safely using correct Oracle binds."""
    
    # FIX: Added UPPER and TRIM to make the lookup bulletproof
    sql = """
        UPDATE expenses
        SET category_id  = (SELECT category_id FROM categories WHERE UPPER(TRIM(category_name)) = UPPER(TRIM(:category_name))),
            amount       = :amount,
            expense_date = TO_DATE(:expense_date, 'YYYY-MM-DD'),
            description  = :description
        WHERE expense_id = :expense_id
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {
                'category_name': category_name, 
                'amount': amount,
                'expense_date': date, 
                'description': description,
                'expense_id': expense_id
            })
        conn.commit()

def delete_expense(expense_id: int):
    """Delete a single expense by primary key."""

    sql = "DELETE FROM expenses WHERE expense_id = :expense_id"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {'expense_id': expense_id})
        conn.commit()

def get_categories():
    sql = "SELECT category_id, category_name FROM categories ORDER BY category_name"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            # Force columns to lowercase dictionary mapping keys
            cols = [d[0].lower() for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def create_user(username, email, plain_password, role_id=2):
    """
    Hashes the password and saves the new user into the database.
    Default role_id is set to 2 (User) if not specified.
    """

    hashed_password = generate_password_hash(plain_password)

    sql = """
        INSERT INTO users(username, email, password_hash, role_id)
        VALUES (:username, :email, :password_hash, :role_id)
    """

    try: 
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {
                    'username': username,
                    'email': email,
                    'password_hash': hashed_password,
                    'role_id': role_id
                })
            conn.commit()
        return True
    except Exception as e:
        print("=== ORACLE SIGNUP ERROR DATABASE LOG ===")
        print(str(e))
        print("========================================")
        return False
    
def verify_user_credentials(email, plain_password):
    """Checks if user exists and verifies their password. 
    Returns the user data dictionary if valid, otherwise None.
    """
    sql = """
        SELECT user_id, username, email, password_hash, role_id
        FROM users
        WHERE LOWER(email) = LOWER(:email)
    """            

    with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {'email': email})
                row = cur.fetchone()
                
                if row:
                    cols = [d[0].lower() for d in cur.description]
                    user_dict = dict(zip(cols, row))
                    
                    # 1. Try checking it as a secure hash first
                    try:
                        if check_password_hash(user_dict['password_hash'], plain_password):
                            return user_dict
                    except ValueError:
                        # If it's not a valid hash format, python will throw a ValueError
                        pass
                    
                    # 2. Fallback: Check if it's stored as plain text (like your '123' record)
                    if user_dict['password_hash'] == plain_password:
                        return user_dict
                
    return None


def get_manager_metrics():
    """Fetch overview aggregate statistics for the manager dashboard."""
    sql_users = "SELECT COUNT(*) FROM users"
    sql_expenses = "SELECT SUM(amount), COUNT(*) FROM expenses"
    sql_status = """
        SELECT 
            SUM(CASE WHEN LOWER(status) = 'pending' THEN 1 ELSE 0 END),
            SUM(CASE WHEN LOWER(status) = 'approved' THEN 1 ELSE 0 END)
        FROM expenses
    """
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Total Users
            cur.execute(sql_users)
            total_users = cur.fetchone()[0] or 0
            
            # Total Expense Amount & Global Count
            cur.execute(sql_expenses)
            exp_row = cur.fetchone()
            total_expenses = float(exp_row[0] or 0)
            
            # Breakdown by Status
            cur.execute(sql_status)
            status_row = cur.fetchone()
            pending_approval = status_row[0] or 0
            approved_expenses = status_row[1] or 0
            
    return {
        'total_users': total_users,
        'total_expenses': total_expenses,
        'pending_approval': pending_approval,
        'approved_expenses': approved_expenses
    }

# Inside db.py

def get_manager_recent_expenses(search_query=None, category_filter=None, sort_option=None):
    """Fetch global user expenses with dynamic filtering and advanced ordering rulesets."""
    params = {}
    where_clauses = []
    
    # Base SELECT mapping logic configuration
    sql = """
        SELECT 
            u.username, 
            c.category_name, 
            e.amount, 
            NVL(e.status, 'Pending') AS status,
            TO_CHAR(e.expense_date, 'DD Mon YYYY') AS expense_date,
            e.expense_id
        FROM expenses e
        JOIN users u ON e.user_id = u.user_id
        LEFT JOIN categories c ON e.category_id = c.category_id
    """
    
    # Apply global cross-field textual pattern searches
    if search_query:
        where_clauses.append("(LOWER(u.username) LIKE :search OR LOWER(e.description) LIKE :search)")
        params['search'] = f"%{search_query.lower()}%"
        
    # Apply category scope constraints
    if category_filter:
        where_clauses.append("LOWER(c.category_name) = :category")
        params['category'] = category_filter.lower()
        
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
        
    # Evaluate Advanced Custom Order Mappings
    sort_rules = {
        'date_desc': "ORDER BY e.expense_date DESC, e.expense_id DESC",
        'date_asc': "ORDER BY e.expense_date ASC, e.expense_id ASC",
        'amount_desc': "ORDER BY e.amount DESC",
        'amount_asc': "ORDER BY e.amount ASC",
        'user_asc': "ORDER BY LOWER(u.username) ASC",
        'user_desc': "ORDER BY LOWER(u.username) DESC",
        # Custom Status Priority Sorting Configuration Matrix (Using CASE weights)
        'status_pending': "ORDER BY CASE WHEN LOWER(e.status)='pending' THEN 0 WHEN LOWER(e.status)='approved' THEN 1 ELSE 2 END ASC, e.expense_date DESC",
        'status_approved': "ORDER BY CASE WHEN LOWER(e.status)='approved' THEN 0 WHEN LOWER(e.status)='pending' THEN 1 ELSE 2 END ASC, e.expense_date DESC",
        'status_rejected': "ORDER BY CASE WHEN LOWER(e.status)='rejected' THEN 0 WHEN LOWER(e.status)='pending' THEN 1 ELSE 2 END ASC, e.expense_date DESC"
    }
    
    # Use selected option or fall back to newest date records order
    sql += "\n " + sort_rules.get(sort_option, "ORDER BY e.expense_date DESC, e.expense_id DESC")
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d[0].lower() for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchmany(50)] # Fetch top 50 matches

def add_category(category_name):
    """Inserts a new category into the database with a pre-calculated color assignment."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Count existing entries to pick the next color in line sequentially
            cur.execute("SELECT COUNT(*) FROM categories")
            count = cur.fetchone()[0] or 0
            
            # 2. Use modulo operator (%) to prevent OutOfIndex bounds crashes
            assigned_color = CAT_COLORS[count % len(CAT_COLORS)]
            
            # 3. Save the new category row with its color profile
            sql = """
                INSERT INTO categories (category_name, category_color) 
                VALUES (:name, :color)
            """
            cur.execute(sql, {'name': category_name.strip(), 'color': assigned_color})
        conn.commit()

def delete_category(category_id):
    """Force delete a category and clean up all associated expenses automatically."""
    sql_delete_expenses = "DELETE FROM expenses WHERE category_id = :id"
    sql_delete_category = "DELETE FROM categories WHERE category_id = :id"

    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Clear out child constraints first
            cur.execute(sql_delete_expenses, {'id': category_id})

            # 2. Clear out the core category asset
            cur.execute(sql_delete_category, {'id': category_id})
        conn.commit()   

def get_all_expenses_raw_dataframe():
    """Fetch complete history rows including dynamic database assigned colors."""
    sql = """
        SELECT 
            u.username, 
            c.category_name, 
            c.category_color,  -- ADDED TO PULL ASSIGNED VALUES FOR MATPLOTLIB
            e.amount, 
            e.expense_date 
        FROM expenses e
        JOIN users u ON e.user_id = u.user_id
        LEFT JOIN categories c ON e.category_id = c.category_id
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            cols = [d[0].lower() for d in cur.description]
            rows = cur.fetchall()
            return pd.DataFrame([dict(zip(cols, r)) for r in rows])
        

def update_expense_status(expense_id, status_string):
    """Update the verification lifecycle status of a specific expense transaction row."""
    # Ensure standard string title casing before storing (Approved / Rejected)
    clean_status = status_string.strip().capitalize()
    
    sql = "UPDATE expenses SET status = :status WHERE expense_id = :id"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {'status': clean_status, 'id': expense_id})
        conn.commit()

# admin

def get_all_users_admin():
    """Fetch all users alongside their structural system roles."""
    sql = """
        SELECT 
            u.user_id, 
            u.username, 
            u.email, 
            u.role_id,
            CASE 
                WHEN u.role_id = 1 THEN 'Admin'
                WHEN u.role_id = 21 THEN 'Manager'
                ELSE 'Regular User'
            END AS role_name
        FROM users u
        ORDER BY u.role_id ASC, LOWER(u.username) ASC
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            cols = [d[0].lower() for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

def update_user_role(target_user_id, new_role_id):
    """Modify the system authorization Role ID clearance for a specific profile."""
    sql = "UPDATE users SET role_id = :role WHERE user_id = :id"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {'role': int(new_role_id), 'id': int(target_user_id)})
        conn.commit()

def admin_delete_user_account(target_user_id):
    """Completely wipe a profile out of the architecture, including historical transactions."""
    sql_delete_expenses = "DELETE FROM expenses WHERE user_id = :id"
    sql_delete_user = "DELETE FROM users WHERE user_id = :id"
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Clean out child foreign key dependencies first
            cur.execute(sql_delete_expenses, {'id': target_user_id})
            
            # 2. Extract the user configuration object row entirely
            cur.execute(sql_delete_user, {'id': target_user_id})
        conn.commit()
