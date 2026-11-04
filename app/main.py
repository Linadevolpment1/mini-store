"""Mini Store: a small online electronics shop."""

import os
import re
import secrets
from datetime import date
from decimal import Decimal

import requests
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from app import store
from app.config import CURRENCY, PAYMENT_API_KEY, PAYMENT_API_URL
from app.db import get_db, init_db
from app.security import admin_required, audit, check_csrf_token, login_required, password_problem

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.before_request(check_csrf_token)


@app.context_processor
def template_globals():
    cart = session.get("cart", {})
    return {"currency": CURRENCY, "cart_count": sum(cart.values())}


# ------------------------------------------------------------------ F2 Catalogue
@app.route("/")
def products():
    conn = get_db()
    text = request.args.get("q", "").strip()
    rows = store.search_products(conn, text) if text else store.list_products(conn)
    conn.close()
    return render_template("products.html", products=rows, q=text)


# ------------------------------------------------------------------ F1 Account
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        f = request.form
        problem = password_problem(f.get("password", ""))
        if not all(f.get(k) for k in ("name", "email", "phone", "address")):
            problem = "Please fill in every field."
        if problem:
            flash(problem)
            return render_template("register.html")
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO users (name, email, phone, address, password_hash) VALUES (?, ?, ?, ?, ?)",
                (f["name"], f["email"].lower(), f["phone"], f["address"], generate_password_hash(f["password"])),
            )
            conn.commit()
        except conn.IntegrityError:
            flash("Could not create the account. Try signing in instead.")
            return render_template("register.html")
        finally:
            conn.close()
        flash("Account created. Please sign in.")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        conn = get_db()
        user = conn.execute(
            "SELECT id, name, role, password_hash FROM users WHERE email = ?",
            (request.form.get("email", "").lower(),),
        ).fetchone()
        conn.close()
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session["user_id"], session["name"], session["role"] = user["id"], user["name"], user["role"]
            return redirect(url_for("products"))
        flash("Invalid email or password.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("products"))


# ------------------------------------------------------------------ F3 Cart and checkout
@app.route("/cart/add", methods=["POST"])
@login_required
def add_to_cart():
    try:
        product_id, quantity = int(request.form["product_id"]), int(request.form.get("quantity", 1))
    except (KeyError, ValueError):
        abort(400)
    cart = session.get("cart", {})
    new_quantity = cart.get(str(product_id), 0) + quantity
    if not 1 <= new_quantity <= 10:
        flash("You can buy between 1 and 10 of each product.")
        return redirect(url_for("products"))
    cart[str(product_id)] = new_quantity
    session["cart"] = cart
    flash("Added to cart.")
    return redirect(url_for("products"))


@app.route("/cart", methods=["GET"])
@login_required
def cart():
    conn = get_db()
    lines = store.cart_lines(conn, session.get("cart", {}))
    conn.close()
    return render_template("cart.html", lines=lines, total=sum(line["subtotal"] for line in lines))


@app.route("/cart/clear", methods=["POST"])
@login_required
def clear_cart():
    session.pop("cart", None)
    return redirect(url_for("cart"))


def charge_payment(amount):
    """Send the charge to the payment provider. Simulated when no provider URL is set (SR-3.4)."""
    if not PAYMENT_API_URL:
        return True
    resp = requests.post(
        PAYMENT_API_URL,
        headers={"Authorization": f"Bearer {PAYMENT_API_KEY}"},
        json={"amount": amount, "currency": CURRENCY},
        timeout=10,
    )
    resp.raise_for_status()
    return True


@app.route("/checkout", methods=["POST"])
@login_required
def checkout():
    conn = get_db()
    lines = store.cart_lines(conn, session.get("cart", {}))
    if not lines:
        conn.close()
        flash("Your cart is empty.")
        return redirect(url_for("cart"))
    code = request.form.get("promo_code", "").strip().upper()
    percent_off, error = store.promo_discount(conn, code, session["user_id"])
    if error:
        conn.close()
        flash(error)
        return redirect(url_for("cart"))
    total = round(sum(line["subtotal"] for line in lines) * (100 - percent_off) / 100, 2)
    try:
        charge_payment(total)
    except requests.RequestException:
        conn.close()
        flash("Payment failed. You have not been charged.")
        return redirect(url_for("cart"))

    customer = conn.execute("SELECT name, phone, address FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    cur = conn.execute(
        "INSERT INTO orders (user_id, created, total, promo_code, ship_name, ship_phone, ship_address) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (session["user_id"], date.today().isoformat(), total, code or None,
         customer["name"], customer["phone"], customer["address"]),
    )
    for line in lines:
        conn.execute(
            "INSERT INTO order_items VALUES (?, ?, ?, ?, ?)",
            (cur.lastrowid, line["id"], line["name"], line["price"], line["quantity"]),
        )
        conn.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (line["quantity"], line["id"]))
    if code:
        conn.execute("INSERT INTO promo_uses VALUES (?, ?)", (code, session["user_id"]))
    conn.commit()
    conn.close()
    session.pop("cart", None)
    flash(f"Thank you! Order #{cur.lastrowid} is placed.")
    return redirect(url_for("order_detail", order_id=cur.lastrowid))


# ------------------------------------------------------------------ F4 Orders
@app.route("/orders")
@login_required
def orders():
    conn = get_db()
    rows = store.orders_for(conn, session["user_id"])
    conn.close()
    return render_template("orders.html", orders=rows)


@app.route("/orders/<int:order_id>")
@login_required
def order_detail(order_id):
    conn = get_db()
    order, items = store.get_order(conn, order_id)
    conn.close()
    if order is None:
        abort(404)
    return render_template("order_detail.html", order=order, items=items)


# ------------------------------------------------------------------ F5 Profile
@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    conn = get_db()
    if request.method == "POST":
        conn.execute(
            "UPDATE users SET phone = ?, address = ? WHERE id = ?",
            (request.form.get("phone", ""), request.form.get("address", ""), session["user_id"]),
        )
        conn.commit()
        flash("Profile updated.")
    user = conn.execute("SELECT name, email, phone, address FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    conn.close()
    return render_template("profile.html", user=user)


@app.route("/profile/password", methods=["POST"])
@login_required
def change_password():
    conn = get_db()
    row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    new = request.form.get("new_password", "")
    if not check_password_hash(row["password_hash"], request.form.get("current_password", "")):
        flash("Your current password is not correct.")
    elif password_problem(new):
        flash(password_problem(new))
    else:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(new), session["user_id"]))
        conn.commit()
        flash("Password changed.")
    conn.close()
    return redirect(url_for("profile"))


# ------------------------------------------------------------------ F6 Admin
@app.route("/admin/products", methods=["GET", "POST"])
@login_required
@admin_required
def admin_products():
    conn = get_db()
    if request.method == "POST":
        raw_price, raw_stock = request.form.get("price", ""), request.form.get("stock", "")
        # Accept plain numbers only, such as 1899 or 1899.50
        if not re.fullmatch(r"\d{1,6}(\.\d{1,2})?", raw_price) or not re.fullmatch(r"\d{1,5}", raw_stock):
            abort(400)
        try:
            product_id = int(request.form["product_id"])
        except (KeyError, ValueError):
            abort(400)
        price, stock = float(Decimal(raw_price)), int(raw_stock)
        if price <= 0:
            abort(400)
        old = conn.execute("SELECT name, price, stock FROM products WHERE id = ?", (product_id,)).fetchone()
        if old is None:
            abort(404)
        conn.execute("UPDATE products SET price = ?, stock = ? WHERE id = ?", (price, stock, product_id))
        audit(conn, f"Changed {old['name']}: price {old['price']} to {price}, stock {old['stock']} to {stock}")
        conn.commit()
        flash(f"{old['name']} updated.")
    rows = store.list_products(conn)
    conn.close()
    return render_template("admin_products.html", products=rows)


@app.route("/admin/orders", methods=["GET", "POST"])
@login_required
@admin_required
def admin_orders():
    conn = get_db()
    if request.method == "POST":
        status = request.form.get("status")
        if status not in ("Placed", "Shipped", "Delivered"):
            abort(400)
        order_id = int(request.form.get("order_id", 0))
        conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        audit(conn, f"Set order #{order_id} to {status}")
        conn.commit()
        flash(f"Order #{order_id} set to {status}.")
    rows = conn.execute(
        "SELECT o.id, o.created, o.total, o.status, u.name FROM orders o JOIN users u ON u.id = o.user_id ORDER BY o.id DESC"
    ).fetchall()
    log = conn.execute(
        "SELECT a.created, u.name, a.action FROM audit_log a LEFT JOIN users u ON u.id = a.user_id ORDER BY a.id DESC LIMIT 20"
    ).fetchall()
    conn.close()
    return render_template("admin_orders.html", orders=rows, log=log)


@app.route("/health")
def health():
    return {"status": "ok"}


init_db()
