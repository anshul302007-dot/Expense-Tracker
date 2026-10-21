
import os
import sqlite3
from datetime import date
from decimal import Decimal, InvalidOperation
from collections import defaultdict

from flask import (
    Flask, render_template, request,
    redirect, url_for, session
)
from werkzeug.security import (
    generate_password_hash, check_password_hash
)

app = Flask(__name__)
app.secret_key = os.environ.get(
    "SECRET_KEY", "development-only-change-before-deploy"
)

DATABASE = "expense.db"

CATEGORIES = [
    "Food", "Travel", "Shopping", "Bills",
    "Education", "Health", "Entertainment",
    "Salary", "Other"
]


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            description TEXT NOT NULL,
            amount_paise INTEGER NOT NULL,
            type TEXT NOT NULL,
            date TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'Other',
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    columns = [
        row["name"] for row in
        conn.execute("PRAGMA table_info(transactions)")
    ]

    if "category" not in columns:
        conn.execute("""
            ALTER TABLE transactions
            ADD COLUMN category TEXT NOT NULL DEFAULT 'Other'
        """)

    conn.commit()
    conn.close()


def validate_transaction(form):
    description = form.get("description", "").strip()
    amount_text = form.get("amount", "")
    transaction_type = form.get("type", "")
    category = form.get("category", "Other")

    if not description or len(description) > 200:
        raise ValueError("Invalid description")

    if transaction_type not in ("income", "expense"):
        raise ValueError("Invalid transaction type")

    if category not in CATEGORIES:
        raise ValueError("Invalid category")

    try:
        amount = Decimal(amount_text)

        if not amount.is_finite() or amount <= 0:
            raise ValueError("Amount must be positive")

        amount_paise = amount * 100

        if amount_paise != amount_paise.to_integral_value():
            raise ValueError("Maximum two decimal places allowed")

        amount_paise = int(amount_paise)

        if amount_paise > 100000000000:
            raise ValueError("Amount is too large")

    except (InvalidOperation, OverflowError):
        raise ValueError("Invalid amount")

    return description, amount_paise, transaction_type, category


@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name or not email or len(password) < 8:
            return "Please fill all fields. Password must be at least 8 characters.", 400

        if password != confirm_password:
            return "Passwords do not match!", 400

        conn = get_db_connection()
        try:
            conn.execute(
                "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                (name, email, generate_password_hash(password))
            )
            conn.commit()
        except sqlite3.IntegrityError:
            return "Email already registered!", 400
        finally:
            conn.close()

        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("dashboard"))

        return "Invalid email or password!", 401

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    user = conn.execute(
        "SELECT name FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    if user is None:
        conn.close()
        session.clear()
        return redirect(url_for("login"))

    transactions = conn.execute("""
        SELECT * FROM transactions
        WHERE user_id = ?
        ORDER BY date DESC, id DESC
    """, (session["user_id"],)).fetchall()

    category_rows = conn.execute("""
        SELECT category, SUM(amount_paise) AS total
        FROM transactions
        WHERE user_id = ? AND type = 'expense'
        GROUP BY category
        ORDER BY total DESC
    """, (session["user_id"],)).fetchall()

    conn.close()

    income_paise = sum(
        t["amount_paise"] for t in transactions
        if t["type"] == "income"
    )

    expense_paise = sum(
        t["amount_paise"] for t in transactions
        if t["type"] == "expense"
    )

    category_totals = [
        {
            "name": row["category"],
            "amount": row["total"] / 100
        }
        for row in category_rows
    ]

    monthly = defaultdict(
        lambda: {"income": 0, "expense": 0}
    )

    for t in transactions:
        month = t["date"][:7]
        monthly[month][t["type"]] += t["amount_paise"]

    months = sorted(monthly.keys())

    monthly_data = {
        "labels": months,
        "income": [
            monthly[m]["income"] / 100 for m in months
        ],
        "expenses": [
            monthly[m]["expense"] / 100 for m in months
        ]
    }

    return render_template(
        "dashboard.html",
        name=user["name"],
        transactions=transactions,
        income=income_paise / 100,
        expense=expense_paise / 100,
        balance=(income_paise - expense_paise) / 100,
        categories=CATEGORIES,
        category_totals=category_totals,
        monthly_data=monthly_data
    )


@app.route("/add_transaction", methods=["POST"])
def add_transaction():
    if "user_id" not in session:
        return redirect(url_for("login"))

    try:
        description, amount, transaction_type, category = (
            validate_transaction(request.form)
        )
    except ValueError as error:
        return str(error), 400

    conn = get_db_connection()

    conn.execute("""
        INSERT INTO transactions
        (user_id, description, amount_paise, type, date, category)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        session["user_id"],
        description,
        amount,
        transaction_type,
        date.today().isoformat(),
        category
    ))

    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))


@app.route("/edit_transaction/<int:transaction_id>", methods=["GET", "POST"])
def edit_transaction(transaction_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    transaction = conn.execute("""
        SELECT * FROM transactions
        WHERE id = ? AND user_id = ?
    """, (transaction_id, session["user_id"])).fetchone()

    if transaction is None:
        conn.close()
        return "Transaction not found", 404

    if request.method == "POST":
        try:
            description, amount, transaction_type, category = (
                validate_transaction(request.form)
            )
        except ValueError as error:
            conn.close()
            return str(error), 400

        conn.execute("""
            UPDATE transactions
            SET description = ?, amount_paise = ?,
                type = ?, category = ?
            WHERE id = ? AND user_id = ?
        """, (
            description, amount, transaction_type,
            category, transaction_id, session["user_id"]
        ))

        conn.commit()
        conn.close()

        return redirect(url_for("dashboard"))

    conn.close()

    return render_template(
        "edit_transaction.html",
        transaction=transaction,
        categories=CATEGORIES
    )


@app.route("/delete_transaction/<int:transaction_id>", methods=["POST"])
def delete_transaction(transaction_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    conn.execute("""
        DELETE FROM transactions
        WHERE id = ? AND user_id = ?
    """, (transaction_id, session["user_id"]))

    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
