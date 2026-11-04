"""Automated tests for Mini Store. They run in the pipeline on every change.

Each security test names the requirement it checks (SR-x.y), so a failing
test points straight back to the requirement it breaks.
"""

import re

import pytest

PASSWORD = "Demo@2026"


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    import importlib

    import app.config
    import app.db
    import app.main

    importlib.reload(app.config)
    importlib.reload(app.db)
    importlib.reload(app.main)
    return app.main.app


def csrf(client):
    page = client.get("/login").get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]*)"', page).group(1)


def post(client, url, data):
    return client.post(url, data={**data, "csrf_token": csrf(client)}, follow_redirects=True)


def signed_in(app, email):
    client = app.test_client()
    post(client, "/login", {"email": email, "password": PASSWORD})
    return client


# ----------------------------------------------------------- features
def test_catalogue_lists_products(app):
    page = app.test_client().get("/").get_data(as_text=True)
    assert "Smartphone X12" in page and "Laptop Air 14" in page


def test_search_filters_by_name(app):
    page = app.test_client().get("/?q=phone").get_data(as_text=True)
    assert "Smartphone X12" in page and "Laptop Air 14" not in page


def test_customer_can_place_an_order(app):
    noura = signed_in(app, "noura@example.com")
    post(noura, "/cart/add", {"product_id": 5, "quantity": 2})
    page = post(noura, "/checkout", {}).get_data(as_text=True)
    assert "is placed" in page and "258" in page


# ----------------------------------------------------------- security requirements
def test_sr_1_1_weak_passwords_are_rejected(app):
    client = app.test_client()
    form = {"name": "A", "email": "a@example.com", "phone": "1", "address": "x"}
    assert "at least 8" in post(client, "/register", {**form, "password": "short"}).get_data(as_text=True)
    assert "too common" in post(client, "/register", {**form, "password": "password1"}).get_data(as_text=True)


def test_sr_1_4_same_error_for_unknown_email_and_wrong_password(app):
    wrong_pw = post(app.test_client(), "/login", {"email": "noura@example.com", "password": "nope"})
    unknown = post(app.test_client(), "/login", {"email": "nobody@example.com", "password": "nope"})
    assert "Invalid email or password" in wrong_pw.get_data(as_text=True)
    assert "Invalid email or password" in unknown.get_data(as_text=True)


def test_sr_3_1_price_comes_from_the_database(app):
    noura = signed_in(app, "noura@example.com")
    post(noura, "/cart/add", {"product_id": 1, "quantity": 1, "price": 1})
    assert "1899" in noura.get("/cart").get_data(as_text=True)


def test_sr_3_2_promo_code_works_once(app):
    noura = signed_in(app, "noura@example.com")
    post(noura, "/cart/add", {"product_id": 5, "quantity": 1})
    assert "is placed" in post(noura, "/checkout", {"promo_code": "WELCOME10"}).get_data(as_text=True)
    post(noura, "/cart/add", {"product_id": 5, "quantity": 1})
    assert "already used" in post(noura, "/checkout", {"promo_code": "WELCOME10"}).get_data(as_text=True)


def test_sr_6_1_customers_cannot_open_admin_pages(app):
    noura = signed_in(app, "noura@example.com")
    assert noura.get("/admin/products").status_code == 403
    assert noura.get("/admin/orders").status_code == 403


def test_sr_g4_forms_without_csrf_token_are_rejected(app):
    response = app.test_client().post("/login", data={"email": "x", "password": "y"})
    assert response.status_code == 400
