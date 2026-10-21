"""Deterministic seed data. No randomness: every reset produces exactly the same store.

Hand-picked rows that tests rely on:
- AUD-008 has stock 3 (stock boundary tests).
- WEA-006 has stock 0 (out-of-stock tests).
- AUD-009 is inactive (soft-deleted products must stay hidden).
- 48 active products with page size 12 gives exactly 4 pages.
- Most prices end in 99, so 8% tax has a fractional cent (rounding tests).
"""

from datetime import datetime, timedelta

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.db import Base
from app.models import Category, Coupon, Product, User
from app.security import hash_password

# Fixed timestamps keep "newest" sorting deterministic across resets.
SEED_BASE_TIME = datetime(2026, 1, 1, 9, 0, 0)
FAR_FUTURE = datetime(2099, 12, 31, 23, 59, 59)
LONG_AGO = datetime(2025, 1, 1, 0, 0, 0)

DEMO_CUSTOMER_EMAIL = "demo@crashcart.test"
DEMO_CUSTOMER_PASSWORD = "demo-password"  # public on purpose: shown on the login page

# fmt: off
# (slug, name, sku prefix, [(product name, price_cents, stock), ...])
CATALOG: list[tuple[str, str, str, list[tuple[str, int, int]]]] = [
    ("audio", "Audio", "AUD", [
        ("Pulse Wireless Earbuds", 4999, 40),
        ("Bassline Over-Ear Headphones", 8999, 25),
        ("Echo Mini Bluetooth Speaker", 2999, 60),
        ("Studio Monitor Headphones", 12999, 15),
        ("Wireless Neckband Earphones", 1999, 50),
        ("Soundbar Lite 2.1", 14999, 10),
        ("Podcast USB Microphone", 6999, 20),
        ("Vinyl-Style Retro Speaker", 5499, 3),
    ]),
    ("wearables", "Wearables", "WEA", [
        ("Stride Fitness Band", 3499, 45),
        ("Orbit Smartwatch S", 15999, 18),
        ("Orbit Smartwatch Pro", 24999, 8),
        ("Heart-Rate Chest Strap", 2499, 30),
        ("Kids GPS Watch", 7999, 12),
        ("Smart Ring Gen 1", 19999, 0),
        ("Sleep Tracker Headband", 9999, 9),
        ("Clip-On Step Counter", 899, 100),
    ]),
    ("smart-home", "Smart Home", "HOM", [
        ("Glow Smart Bulb 2-Pack", 1999, 80),
        ("Smart Plug Duo", 1299, 90),
        ("Video Doorbell Basic", 8999, 14),
        ("Indoor Security Camera", 4499, 22),
        ("Smart Thermostat Lite", 12999, 7),
        ("Motion Sensor Kit", 3999, 35),
        ("Robot Vacuum Mini", 21999, 5),
        ("Voice Hub Speaker", 5999, 26),
    ]),
    ("computer-accessories", "Computer Accessories", "CMP", [
        ("Wireless Silent Mouse", 1499, 70),
        ("Mechanical Keyboard TKL", 7999, 20),
        ("USB-C Hub 7-in-1", 3999, 40),
        ("Single Monitor Arm", 4999, 15),
        ("Aluminium Laptop Stand", 2999, 33),
        ("Webcam 1080p", 4499, 28),
        ("External SSD 1TB", 9999, 16),
        ("Ergonomic Wrist Rest", 1199, 55),
    ]),
    ("phone-accessories", "Phone Accessories", "PHN", [
        ("Wireless Charger Pad", 2499, 60),
        ("Fast Charger 30W", 1999, 75),
        ("Braided USB-C Cable 2m", 999, 120),
        ("Power Bank 20000mAh", 4999, 30),
        ("Car Phone Mount", 1599, 44),
        ("Clear Phone Case", 799, 150),
        ("Tempered Glass Screen Protector", 899, 140),
        ("Selfie Stick Tripod", 2299, 25),
    ]),
    ("gaming", "Gaming", "GAM", [
        ("Wireless Game Controller", 5999, 30),
        ("RGB Gaming Headset", 6999, 20),
        ("Gaming Mouse Pro", 4999, 25),
        ("XL Desk Mat", 1999, 50),
        ("Controller Charging Dock", 2499, 35),
        ("Streaming Capture Card", 13999, 6),
        ("Racing Wheel Starter", 19999, 4),
        ("Retro Handheld Console", 8999, 10),
    ]),
]

INACTIVE_PRODUCT = ("audio", "AUD-009", "Discontinued Cassette Player", 2999)

# (code, kind, value, min_subtotal_cents, expires_at, max_uses, used_count)
COUPONS = [
    ("SAVE10", "percent", 10, 0, FAR_FUTURE, None, 0),
    ("FLAT5", "fixed", 500, 2000, FAR_FUTURE, None, 0),
    ("BIGSPEND20", "percent", 20, 10000, FAR_FUTURE, None, 0),
    ("EXPIRED15", "percent", 15, 0, LONG_AGO, None, 0),
    ("USEDUP", "fixed", 1000, 0, FAR_FUTURE, 1, 1),  # already used up
]
# fmt: on


def _description(name: str, category: str) -> str:
    return f"{name} from the CrashCart {category} range. A fictional product for a demo store."


def seed(session: Session, settings: Settings) -> None:
    categories: dict[str, Category] = {}
    product_index = 0
    for slug, cat_name, prefix, products in CATALOG:
        category = Category(name=cat_name, slug=slug)
        session.add(category)
        categories[slug] = category
        for number, (name, price, stock) in enumerate(products, start=1):
            sku = f"{prefix}-{number:03d}"
            session.add(
                Product(
                    sku=sku,
                    name=name,
                    description=_description(name, cat_name),
                    category=category,
                    price_cents=price,
                    stock=stock,
                    image_path=f"/img/products/{sku.lower()}.svg",
                    created_at=SEED_BASE_TIME + timedelta(days=product_index),
                    updated_at=SEED_BASE_TIME + timedelta(days=product_index),
                )
            )
            product_index += 1

    slug, sku, name, price = INACTIVE_PRODUCT
    session.add(
        Product(
            sku=sku,
            name=name,
            description=_description(name, categories[slug].name),
            category=categories[slug],
            price_cents=price,
            stock=0,
            image_path=f"/img/products/{sku.lower()}.svg",
            is_active=False,
            created_at=SEED_BASE_TIME,
            updated_at=SEED_BASE_TIME,
        )
    )

    for code, kind, value, min_subtotal, expires_at, max_uses, used in COUPONS:
        session.add(
            Coupon(
                code=code,
                kind=kind,
                value=value,
                min_subtotal_cents=min_subtotal,
                expires_at=expires_at,
                max_uses=max_uses,
                used_count=used,
            )
        )

    rounds = settings.bcrypt_rounds
    session.add_all(
        [
            User(
                email=settings.admin_email.lower(),
                password_hash=hash_password(settings.admin_password, rounds),
                full_name="Store Admin",
                role="admin",
                created_at=SEED_BASE_TIME,
            ),
            User(
                email=DEMO_CUSTOMER_EMAIL,
                password_hash=hash_password(DEMO_CUSTOMER_PASSWORD, rounds),
                full_name="Demo Shopper",
                role="customer",
                created_at=SEED_BASE_TIME,
            ),
        ]
    )


def reset_database(
    engine: Engine, session_factory: sessionmaker[Session], settings: Settings
) -> None:
    """Drop every table and recreate the seed state."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with session_factory() as session:
        seed(session, settings)
        session.commit()
