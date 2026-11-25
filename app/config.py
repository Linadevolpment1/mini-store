"""Settings for Mini Store.

WARNING: this file contains a deliberately planted secret for a
DevSecOps demo. The key below is fake and grants no access.
"""

import os

DATABASE_PATH = os.environ.get("DATABASE_PATH", "store.db")
CURRENCY = "SAR"

# Payment provider (simulated in this demo)
PAYMENT_API_URL = os.environ.get("PAYMENT_API_URL")
PAYMENT_API_KEY = os.environ.get("PAYMENT_API_KEY")
IMAGES_ACCESS_KEY_ID = os.environ.get("IMAGES_ACCESS_KEY_ID")