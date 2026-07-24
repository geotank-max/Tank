-- =========================
-- 1. ROLES
-- =========================
CREATE TABLE roles (
    role_id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    role_name VARCHAR2(50) NOT NULL UNIQUE
);

-- =========================
-- 2. USERS
-- =========================
CREATE TABLE users (
    user_id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username VARCHAR2(100) NOT NULL,
    email VARCHAR2(150) NOT NULL UNIQUE,
    password_hash VARCHAR2(255) NOT NULL,
    role_id NUMBER NOT NULL,

    CONSTRAINT fk_users_role
        FOREIGN KEY (role_id)
        REFERENCES roles(role_id)
);

-- =========================
-- 3. CATEGORIES
-- =========================
CREATE TABLE categories (
    category_id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    category_name VARCHAR2(100) NOT NULL UNIQUE
);

-- =========================
-- 4. EXPENSES
-- =========================
CREATE TABLE expenses (
    expense_id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id NUMBER NOT NULL,
    category_id NUMBER NOT NULL,

    amount NUMBER(10,2) NOT NULL,
    expense_date DATE DEFAULT SYSDATE,
    description VARCHAR2(255),

    CONSTRAINT chk_expense_amount
        CHECK (amount > 0),

    CONSTRAINT fk_expense_user
        FOREIGN KEY (user_id)
        REFERENCES users(user_id),

    CONSTRAINT fk_expense_category
        FOREIGN KEY (category_id)
        REFERENCES categories(category_id)
);

-- =========================
-- 5. INCOME
-- =========================
CREATE TABLE income (
    income_id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id NUMBER NOT NULL,

    amount NUMBER(10,2) NOT NULL,
    income_date DATE DEFAULT SYSDATE,
    source VARCHAR2(100),

    CONSTRAINT chk_income_amount
        CHECK (amount > 0),

    CONSTRAINT fk_income_user
        FOREIGN KEY (user_id)
        REFERENCES users(user_id)
);

-- =========================
-- 6. BUDGETS
-- =========================
CREATE TABLE budgets (
    budget_id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id NUMBER NOT NULL,
    category_id NUMBER NOT NULL,

    amount_limit NUMBER(10,2) NOT NULL,
    budget_month NUMBER(2) NOT NULL,
    budget_year NUMBER(4) NOT NULL,

    CONSTRAINT chk_budget_amount
        CHECK (amount_limit > 0),

    CONSTRAINT chk_budget_month
        CHECK (budget_month BETWEEN 1 AND 12),

    CONSTRAINT fk_budget_user
        FOREIGN KEY (user_id)
        REFERENCES users(user_id),

    CONSTRAINT fk_budget_category
        FOREIGN KEY (category_id)
        REFERENCES categories(category_id)
);