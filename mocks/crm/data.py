"""Deterministic CRM dataset: 60 Indian customers with KYC fields and order history.

Four customers are hand-written because the demo scenario depends on them;
the rest come from Faker `en_IN` with a fixed seed so every run is identical.
"""

from __future__ import annotations

import random
from functools import lru_cache

from faker import Faker
from pydantic import BaseModel, Field

SEED = 20261012
TOTAL_CUSTOMERS = 60
BANKS = ["okhdfcbank", "okicici", "oksbi", "ybl", "paytm", "okaxis"]


class Order(BaseModel):
    order_id: str
    item: str
    amount_inr: int
    charges_inr: list[int]  # every charge seen by the gateway; two equal entries = duplicate charge
    date: str
    status: str = "delivered"


class Customer(BaseModel):
    customer_id: str
    name: str
    email: str
    phone: str
    city: str
    address: str
    pan: str
    aadhaar_last4: str
    verified_upi: str
    verified_account: str
    bank: str
    created_at: str
    notes: str = ""
    orders: list[Order] = Field(default_factory=list)


ITEMS = [
    ("Personal loan EMI", 6500, 24000),
    ("Gold loan processing fee", 999, 4999),
    ("Consumer durable EMI", 1499, 12999),
    ("Two-wheeler loan EMI", 2800, 7800),
    ("Insurance premium", 1200, 18000),
]


def _pan(rng: random.Random, surname: str) -> str:
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    initial = (surname[:1] or "K").upper()
    return (
        "".join(rng.choice(letters) for _ in range(3))
        + "P"
        + initial
        + f"{rng.randint(1000, 9999)}"
        + rng.choice(letters)
    )


def _fixed_customers() -> dict[int, Customer]:
    """Scenario actors pinned to fixed ids so plans and tests can reference them."""
    return {
        7: Customer(
            customer_id="C1007",
            name="Ravi Kumar",
            email="ravi.kumar@gmail.com",
            phone="+91 98450 31277",
            city="Bengaluru",
            address="No. 44, 2nd Cross, Indiranagar, Bengaluru 560038",
            pan="BQRPK4821M",
            aadhaar_last4="4821",
            verified_upi="ravikumar.blr@okicici",
            verified_account="HDFC0001234 · XXXXXXXX4821",
            bank="HDFC Bank",
            created_at="2023-02-14",
            orders=[
                Order(
                    order_id="#A-7731",
                    item="Consumer durable EMI — LG refrigerator",
                    amount_inr=48000,
                    charges_inr=[48000, 48000],
                    date="2026-10-11",
                ),
                Order(
                    order_id="#A-6120",
                    item="Gold loan processing fee",
                    amount_inr=1299,
                    charges_inr=[1299],
                    date="2026-08-03",
                ),
            ],
        ),
        12: Customer(
            customer_id="C1012",
            name="Priya Sharma",
            email="priya.sharma@yahoo.co.in",
            phone="+91 99230 55410",
            city="Pune",
            address="B-302, Kumar Pebble Park, Hadapsar, Pune 411028",
            pan="AHTPS7710K",
            aadhaar_last4="5531",
            verified_upi="priyasharma@oksbi",
            verified_account="SBIN0004567 · XXXXXXXX9902",
            bank="State Bank of India",
            created_at="2022-11-02",
            orders=[
                Order(
                    order_id="#B-1180",
                    item="Two-wheeler loan EMI",
                    amount_inr=4200,
                    charges_inr=[4200],
                    date="2026-10-05",
                )
            ],
        ),
        23: Customer(
            customer_id="C1023",
            name="Arjun Mehta",
            email="arjun.mehta@outlook.com",
            phone="+91 98200 77345",
            city="Mumbai",
            address="12, Sea Breeze CHS, Bandra West, Mumbai 400050",
            pan="CKLPM3348Q",
            aadhaar_last4="7710",
            verified_upi="arjunm@okhdfcbank",
            verified_account="ICIC0000456 · XXXXXXXX7710",
            bank="ICICI Bank",
            created_at="2024-01-20",
            orders=[
                Order(
                    order_id="#B-2210",
                    item="Gold loan processing fee",
                    amount_inr=2499,
                    charges_inr=[2499],
                    date="2026-10-09",
                    status="cancelled",
                )
            ],
        ),
        31: Customer(
            customer_id="C1031",
            name="Ananya Iyer",
            email="ananya.iyer@gmail.com",
            phone="+91 94440 12876",
            city="Chennai",
            address="Flat 6, Lotus Apartments, Adyar, Chennai 600020",
            pan="DMNPI9054R",
            aadhaar_last4="3390",
            verified_upi="ananya.iyer@ybl",
            verified_account="UTIB0002233 · XXXXXXXX3390",
            bank="Axis Bank",
            created_at="2021-07-11",
            orders=[
                Order(
                    order_id="#C-4402",
                    item="Personal loan EMI",
                    amount_inr=12800,
                    charges_inr=[12800],
                    date="2026-09-05",
                ),
                Order(
                    order_id="#C-4519",
                    item="Personal loan EMI",
                    amount_inr=12800,
                    charges_inr=[12800],
                    date="2026-10-05",
                ),
            ],
        ),
    }


@lru_cache(maxsize=1)
def generate_customers() -> tuple[Customer, ...]:
    """Build the 60-customer book once per process; the result is immutable and shared."""
    fake = Faker("en_IN")
    Faker.seed(SEED)
    rng = random.Random(SEED)
    fixed = _fixed_customers()
    customers: list[Customer] = []
    used_emails: set[str] = {c.email for c in fixed.values()}
    for idx in range(1, TOTAL_CUSTOMERS + 1):
        if idx in fixed:
            customers.append(fixed[idx])
            continue
        first, last = fake.first_name(), fake.last_name()
        handle = f"{first}.{last}".lower().replace(" ", "")
        email = f"{handle}@{rng.choice(['gmail.com', 'yahoo.co.in', 'outlook.com', 'rediffmail.com'])}"
        if email in used_emails:
            email = f"{handle}{idx}@gmail.com"
        used_emails.add(email)
        last4 = f"{rng.randint(1000, 9999)}"
        orders = []
        for n in range(rng.randint(1, 3)):
            item, lo, hi = rng.choice(ITEMS)
            amount = rng.randint(lo, hi) // 10 * 10 - 1
            orders.append(
                Order(
                    order_id=f"#{rng.choice('ABCDE')}-{rng.randint(1000, 9999)}",
                    item=item,
                    amount_inr=amount,
                    charges_inr=[amount],
                    date=f"2026-{rng.randint(6, 10):02d}-{rng.randint(1, 28):02d}",
                    status="delivered" if n else rng.choice(["delivered", "active"]),
                )
            )
        customers.append(
            Customer(
                customer_id=f"C{1000 + idx}",
                name=f"{first} {last}",
                email=email,
                phone=f"+91 {rng.randint(70000, 99999)} {rng.randint(10000, 99999)}",
                city=fake.city(),
                address=fake.address().replace("\n", ", "),
                pan=_pan(rng, last),
                aadhaar_last4=f"{rng.randint(1000, 9999)}",
                verified_upi=f"{handle.replace('.', '')}@{rng.choice(BANKS)}",
                verified_account=f"{rng.choice(['HDFC', 'ICIC', 'SBIN', 'UTIB', 'KKBK'])}000{rng.randint(1000, 9999)} · XXXXXXXX{last4}",
                bank=rng.choice(
                    ["HDFC Bank", "ICICI Bank", "State Bank of India", "Axis Bank", "Kotak Mahindra Bank"]
                ),
                created_at=f"20{rng.randint(19, 26)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
                orders=orders,
            )
        )
    return tuple(customers)
