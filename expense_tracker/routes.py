
from pathlib import Path

from flask import Flask, render_template, request, redirect, flash, url_for, session 
import pandas as pd
from functools import wraps

from . import chart, db


BASE_DIR = Path(__file__).resolve().parent.parent

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)

app.secret_key = 'expensevault-secret-2024-change-in-production'

#1. Access Control Decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# manager required

def manager_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in first.", "error")
            return redirect(url_for('login'))
        if session.get('role_id') not in [21,1]:
            flash("Access denied. Managers only.", "error")
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in first.", "error")
            return redirect(url_for('login'))
        if session.get('role_id') != 1:  # Strict verification check against Admin Role ID
            flash("Access denied. Administrative security clearance required.", "error")
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

#2. Secure your home/Dashboard route
@app.route("/")
@login_required
def home():
    user_id = session['user_id']
    
    # 1. Fetch entire historical records for Pandas aggregations and analytics
    rows = db.get_all_expenses(user_id)

    if not rows or len(rows) == 0:
        return render_template('expense.html',
                               total=0, count=0, average=0, max_expense=0,
                               top_category='-', category_data={}, recent=[],
                               pie_chart=None, monthly_line=None, category_chart=None)
                               
    df = pd.DataFrame(rows)
    
    # 2. Clean numeric calculations using lowercase keys
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)

    # 3. Compute metric overview figures
    total = df['amount'].sum()
    count = len(df)
    average = df['amount'].mean()
    max_expense = df['amount'].max()
    
    try:
        top_category = df.groupby('category_name')['amount'].sum().idxmax()
        category_data = df.groupby('category_name')['amount'].sum().sort_values(ascending=False).to_dict()
    except Exception:
        top_category = '-'
        category_data = {}

    # 4. FIX: Load structured records directly via Oracle SQL engine instead of Pandas slicing
    # This guarantees c.category_color is present and correctly structured for your color badges!
    recent = db.get_recent_expenses(user_id)

    # 5. Build user-specific data visualization charts
    pie_chart = chart.generate_category_pie(df, user_id)
    monthly_line = chart.generate_monthly_bar(df, user_id)
    category_chart = chart.generate_category_chart(df, user_id)

    return render_template("expense.html", 
                            total=total, count=count, average=average,
                            max_expense=max_expense, top_category=top_category,
                            category_data=category_data, recent=recent,
                            pie_chart=pie_chart,
                            monthly_line=monthly_line, category_chart=category_chart)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", '').strip()
        email = request.form.get("email", '').strip()
        password = request.form.get("password", '').strip()

        role_id = 2

        if not username or not email or not password:
            flash("All fields are required.", "error")
            return render_template("signup.html")
        
        success = db.create_user(username, email, password, role_id)
        if success:
            flash("Account created successfully! Please log in.", "success")
            return redirect(url_for('login'))
        else:
            flash("Email might already be registered. Try a different one.", "error")

    return render_template("signup.html")


#4. Login Route
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", '').strip()
        password = request.form.get("password", '').strip()

        user = db.verify_user_credentials(email, password)

        if user: 
            # Save user identity variable inside the session storage
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            session['email'] = user['email']
            session['role_id'] = user['role_id']

            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(url_for('home'))
        else: 
            flash("Invalid email or password.", "error")

    return render_template("login.html")

@app.route('/logout')
def logout():
    session.clear() #completely wipes out session tracking
    flash("You have successfully logged out.", 'success')
    return redirect(url_for('login'))

@app.route("/add", methods=["GET", "POST"])
@login_required #everyone logged-in can access now
def add_expense():
    if request.method == "POST":
        category = request.form.get('category', '').strip()
        if not category:
            errors.append('Please select an operational category.')
        
        amount = request.form["amount"].strip()
        date = request.form["date"]
        description = request.form.get("description", '').strip()

        errors = []
        
        try: 
            amount_f = float(amount)
            if amount_f <= 0:
                errors.append('Amount must be greater than 0.')
        except ValueError:
            errors.append('Amount must be a number.')

        if not date:
            errors.append('Date is required.')

        if errors: 
            for e in errors:
                flash(e, 'error')

            # FIX: Added .html extension
            return render_template('expense_form.html',
                                   categories=db.get_categories(),
                                   form=request.form)
        
        try:
            db.add_expense(session['user_id'], category, amount_f, date, description)
            # FIX: Typo in "added"
            flash("Expense added successfully!", 'success')
            return redirect(url_for('all_expenses'))
        except Exception as e:
            flash(f"Database Error: {str(e)}", 'error')
            return render_template('expense_form.html', categories=db.get_categories(), form=request.form)
    
    return render_template('expense_form.html',
                           categories=db.get_categories(), form={})

@app.route("/expenses")
@login_required
def all_expenses():

    search = request.args.get("search", '').strip()
    category = request.args.get('category', '').strip()
    sort = request.args.get("sort", "date_desc")

    expense_df = db.get_filterd_expenses(session['user_id'],category, search, sort)
    total_filtered =  expense_df['amount'].sum()
    expenses = expense_df.to_dict("records")

    categories = db.get_categories()

    return render_template('all_expenses.html',
        expenses=expenses,
        categories=categories,
        selected_category=category,
        search=search,
        sort = sort,
        total_filtered=total_filtered,                       
    )

@app.route("/edit/<int:expense_id>", methods=["GET", "POST"])
def edit_expense(expense_id):

    expense = db.get_expense_by_id(expense_id)
    if not expense:
        flash('Expense not found.', 'error')
        return redirect(url_for('all_expenses'))
    
    if request.method == "POST":
        # FIX: Changed square brackets to .get() method
        category = request.form.get('category', 'Other') 
        amount = request.form["amount"].strip()
        date = request.form["date"]
        description = request.form.get("description", '').strip()

        errors = []
        try:
            amount_f = float(amount)
            if amount_f <= 0:
                errors.append('Amount must be greater than 0.')
        except ValueError:
            errors.append('Amount must be a number.')

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('edit_expense.html',
                                   expense=expense, categories=db.get_categories())

        try:
            db.update_expense(expense_id, amount_f, category, date, description)
            flash(f'"{category}" updated.', 'success')
            return redirect(url_for('all_expenses'))
        except Exception as e:
            flash(f"Updated failed: {str(e)}", 'error')
            return render_template('edit_expense.html', expense=expense, categories=db.get_categories())

    return render_template('edit_expense.html',
                            expense=expense, categories=db.get_categories())

@app.route("/delete/<int:expense_id>", methods=['POST'])
def delete_expense(expense_id):
    expense = db.get_expense_by_id(expense_id)
    if expense:
        db.delete_expense(expense_id)
        flash(f'Deleted {expense["category_name"]} expense of ${expense["amount"]:.2f}.', 'info')
    else:
        flash('Expense not found.', 'error')
        
    return redirect(url_for('all_expenses'))



@app.route("/manager/dashboard")
@manager_required
def manager_dashboard():
    # Capture incoming request.args from our toolbar form submission
    search = request.args.get('search', '').strip()
    selected_category = request.args.get('category', '').strip()
    sort = request.args.get('sort', 'date_desc').strip()
    
    # Load administrative list variables
    categories = db.get_categories() 
    metrics = db.get_manager_metrics()
    
    # Fetch dynamically filtered and sorted transaction history records
    recent_transactions = db.get_manager_recent_expenses(
        search_query=search, 
        category_filter=selected_category, 
        sort_option=sort
    )
    
    # Charts engine compilation blocks 
    global_df = db.get_all_expenses_raw_dataframe()
    pie_chart = chart.generate_global_category_pie(global_df)
    monthly_line = chart.generate_global_monthly_line(global_df)
    user_chart = chart.generate_global_user_bar(global_df)
    
    return render_template('manager_dashboard.html', 
                           metrics=metrics, 
                           recent=recent_transactions,
                           categories=categories,
                           search=search,
                           selected_category=selected_category,
                           sort=sort,
                           pie_chart=pie_chart,
                           monthly_line=monthly_line,
                           user_chart=user_chart)

@app.route("/manager/categories", methods=["GET", "POST"])
@manager_required
def manage_categories():
    if request.method == "POST":
        new_cat = request.form.get("category_name", "").strip()
        if new_cat:
            try:
                db.add_category(new_cat)
                flash(f"Category '{new_cat}' added successfully!", "success")
            except Exception as e:
                flash(f"Error adding category: {str(e)}", "error")
        else:
            flash("Category name cannot be empty.", "error")
        return redirect(url_for('manage_categories'))

    # GET requests fetch current list
    categories = db.get_categories() # Assumes a method returning category dict records
    return render_template('manager_categories.html', categories=categories)

@app.route("/manager/categories/delete/<int:category_id>", methods=["POST"])
@manager_required
def remove_category(category_id):
    try:
        db.delete_category(category_id)
        flash("Category removed successfully.", "info")
    except Exception as e:
        flash("Cannot delete category currently linked to user transactions.", "error")
    return redirect(url_for('manage_categories'))

@app.route("/manager/expenses/<int:expense_id>/status", methods=["POST"])
@manager_required
def update_status(expense_id):
    action = request.form.get('action', '').lower()
    
    if action == 'approve':
        db.update_expense_status(expense_id, 'Approved')
        flash("Transaction approved successfully.", "success")
    elif action == 'reject':
        db.update_expense_status(expense_id, 'Rejected')
        flash("Transaction rejected successfully.", "info")
    else:
        flash("Invalid administrative action request.", "error")
        
    return redirect(url_for('manager_dashboard'))

# admin route

@app.route("/admin/users")
@admin_required
def admin_manage_users():
    """Display the full user registry control grid dashboard panel."""
    users_list = db.get_all_users_admin()
    return render_template('admin_users.html', users=users_list)

@app.route("/admin/users/<int:target_user_id>/role", methods=["POST"])
@admin_required
def admin_assign_role(target_user_id):
    """Assign or downgrade system structural authorization positions."""
    # Prevent the active admin from accidentally overwriting their own root access block
    if target_user_id == session.get('user_id'):
        flash("Safety Lock: You cannot alter your own admin permissions.", "error")
        return redirect(url_for('admin_manage_users'))
        
    new_role = request.form.get('role_id')
    if new_role in ['1', '2', '21']: # Valid system assignments matrix
        try:
            db.update_user_role(target_user_id, new_role)
            flash("User clearance matrix assigned successfully.", "success")
        except Exception as e:
            flash(f"Role alignment crash: {str(e)}", "error")
    return redirect(url_for('admin_manage_users'))

@app.route("/admin/users/<int:target_user_id>/delete", methods=["POST"])
@admin_required
def admin_drop_account(target_user_id):
    """Force remove a user file asset completely."""
    if target_user_id == session.get('user_id'):
        flash("Safety Lock: You cannot delete your own active administrative profile account.", "error")
        return redirect(url_for('admin_manage_users'))
        
    try:
        db.admin_delete_user_account(target_user_id)
        flash("Account record data asset successfully dropped from systemic server architecture.", "info")
    except Exception as e:
        flash(f"Account destruction execution failed: {str(e)}", "error")
    return redirect(url_for('admin_manage_users'))

if __name__ == "__main__":
    app.run(debug=True)
