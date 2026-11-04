"""Catalogue, cart and order logic.

WARNING: contains a deliberately planted SQL injection for a DevSecOps demo.
"""

from datetime import date


def list_products(conn):
    return conn.execute("SELECT id, name, description, price, stock FROM products ORDER BY id").fetchall()


def search_products(conn, text):
    query = f"SELECT id, name, description, price, stock FROM products WHERE name LIKE '%{text}%' ORDER BY id"
    return conn.execute(query).fetchall()


def cart_lines(conn, cart):
    """Turn the session cart {product_id: quantity} into lines priced from the database (SR-3.1)."""
    lines = []
    for product_id, quantity in cart.items():
        row = conn.execute("SELECT id, name, price FROM products WHERE id = ?", (int(product_id),)).fetchone()
        if row:
            lines.append({"id": row["id"], "name": row["name"], "price": row["price"], "quantity": quantity,
                          "subtotal": row["price"] * quantity})
    return lines


def promo_discount(conn, code, user_id):
    """Return (percent_off, error). A code works once per customer, before it expires (SR-3.2)."""
    if not code:
        return 0, None
    promo = conn.execute("SELECT percent_off, expires FROM promo_codes WHERE code = ?", (code.upper(),)).fetchone()
    if promo is None:
        return 0, "That promo code does not exist."
    if date.fromisoformat(promo["expires"]) < date.today():
        return 0, "That promo code has expired."
    used = conn.execute("SELECT 1 FROM promo_uses WHERE code = ? AND user_id = ?", (code.upper(), user_id)).fetchone()
    if used:
        return 0, "You have already used that promo code."
    return promo["percent_off"], None


def orders_for(conn, user_id):
    return conn.execute(
        "SELECT id, created, total, status FROM orders WHERE user_id = ? ORDER BY id DESC", (user_id,)
    ).fetchall()


def get_order(conn, order_id):
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    items = conn.execute("SELECT name, price, quantity FROM order_items WHERE order_id = ?", (order_id,)).fetchall()
    return order, items
