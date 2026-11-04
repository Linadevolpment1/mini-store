"""Database setup for Mini Store (SQLite)."""

import os
import sqlite3

import yaml
from werkzeug.security import generate_password_hash

from app.config import DATABASE_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT,
    email TEXT UNIQUE,
    phone TEXT,
    address TEXT,
    password_hash TEXT,
    role TEXT DEFAULT 'customer'
);
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY,
    name TEXT,
    description TEXT,
    price REAL,
    stock INTEGER
);
CREATE TABLE IF NOT EXISTS promo_codes (
    code TEXT PRIMARY KEY,
    percent_off INTEGER,
    expires TEXT
);
CREATE TABLE IF NOT EXISTS promo_uses (
    code TEXT,
    user_id INTEGER,
    PRIMARY KEY (code, user_id)
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    created TEXT,
    total REAL,
    promo_code TEXT,
    status TEXT DEFAULT 'Placed',
    ship_name TEXT,
    ship_phone TEXT,
    ship_address TEXT
);
CREATE TABLE IF NOT EXISTS order_items (
    order_id INTEGER,
    product_id INTEGER,
    name TEXT,
    price REAL,
    quantity INTEGER
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY,
    created TEXT,
    user_id INTEGER,
    action TEXT
);
"""


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)
    if conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        seed(conn)
    conn.commit()
    conn.close()


def seed(conn):
    with open(os.path.join(os.path.dirname(__file__), "catalogue.yaml"), encoding="utf-8") as f:
        data = yaml.safe_load(f)
    for p in data["products"]:
        conn.execute(
            "INSERT INTO products (name, description, price, stock) VALUES (?, ?, ?, ?)",
            (p["name"], p["description"], p["price"], p["stock"]),
        )
    for c in data["promo_codes"]:
        conn.execute("INSERT INTO promo_codes VALUES (?, ?, ?)", (c["code"], c["percent_off"], str(c["expires"])))

    # Demo accounts. They all share one demo password, set with DEMO_PASSWORD.
    pw = generate_password_hash(os.environ.get("DEMO_PASSWORD", "Demo@2026"))
    people = [
        ("Noura Alotaibi", "noura@example.com", "0550000001", "Olaya St, Riyadh", "customer"),
        ("Faisal Alshehri", "faisal@example.com", "0550000002", "Tahlia St, Jeddah", "customer"),
        ("Store Admin", "admin@ministore.example", "0550000000", "Mini Store HQ, Riyadh", "admin"),
    ]
    for name, email, phone, address, role in people:
        conn.execute(
            "INSERT INTO users (name, email, phone, address, password_hash, role) VALUES (?, ?, ?, ?, ?, ?)",
            (name, email, phone, address, pw, role),
        )
    # One earlier order for Faisal, so the order history is not empty
    conn.execute(
        "INSERT INTO orders (user_id, created, total, status, ship_name, ship_phone, ship_address) "
        "VALUES (2, '2026-10-20', 2348, 'Delivered', 'Faisal Alshehri', '0550000002', 'Tahlia St, Jeddah')"
    )
    conn.execute("INSERT INTO order_items VALUES (1, 1, 'Smartphone X12', 1899, 1)")
    conn.execute("INSERT INTO order_items VALUES (1, 2, 'Wireless Earbuds Pro', 449, 1)")
