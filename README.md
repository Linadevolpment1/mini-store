# Mini Store

A small online electronics shop. Customers register, browse and search products, place orders with a promo code, and track them. An admin manages products and order status.

It is the practice app for a DevSecOps demo, built from the Mini Store requirements (features F1 to F6, security requirements SR-1.1 to SR-G7).

> ⚠️ This app contains **deliberate security flaws** for a training demo. The payment key in `app/config.py` is made up and grants no access. Do not deploy it anywhere.

## Demo accounts

Password for all three: `Demo@2026`

| Email | Name | Role |
|---|---|---|
| `noura@example.com` | Noura Alotaibi | Customer |
| `faisal@example.com` | Faisal Alshehri | Customer (has one past order) |
| `admin@ministore.example` | Store Admin | Admin |

Promo code: `WELCOME10` (10% off, once per customer). Payment is simulated, so no card details are ever entered.

## Features

| ID | Feature | Pages |
|---|---|---|
| F1 | Register and sign in | `/register`, `/login` |
| F2 | Browse and search products | `/`, `/?q=phone` |
| F3 | Cart and checkout with promo code | `/cart` |
| F4 | Order history and order details | `/orders`, `/orders/<number>` |
| F5 | Profile: phone, address, password | `/profile` |
| F6 | Admin: products, orders, audit log | `/admin/products`, `/admin/orders` |

## How it is built

```
Browser ──▶ Flask web app (Python) ──▶ SQLite database (users, products, orders, audit log)
                  │
                  └──▶ Payment provider (simulated; uses an API key)
```

| File | What it does |
|---|---|
| `app/main.py` | All pages and actions |
| `app/store.py` | Product search, cart pricing, promo codes, orders |
| `app/security.py` | Password rules, sign-in and admin checks, CSRF protection, audit log |
| `app/db.py` | Creates the database and the demo data |
| `app/config.py` | Settings |
| `app/catalogue.yaml` | Starting products and promo codes |
| `app/templates/` | The HTML pages |
| `requirements.txt` | Third-party libraries |
| `Dockerfile` | Packages the app as a container |

## Run it on your laptop

With Python 3.12:
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
flask --app app.main run
```
Open http://localhost:5000

Or with Docker:
```bash
docker build -t mini-store .
docker run --rm -p 8000:8000 mini-store
```
Open http://localhost:8000
