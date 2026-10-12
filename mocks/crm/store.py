"""SQLite-backed CRM. Each World gets its own in-memory copy so demo lanes never interfere."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from mocks.crm.data import Customer, generate_customers

SCHEMA = """
CREATE TABLE customers (
    customer_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT NOT NULL,
    city TEXT NOT NULL,
    created_at TEXT NOT NULL,
    record TEXT NOT NULL,
    -- Provenance persisted with the data: an address typed by a customer in an email
    -- must not come back out of the CRM looking like a verified, trusted value.
    address_provenance TEXT NOT NULL DEFAULT 'kyc_verified'
);
"""


class CRM:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self._load(generate_customers())

    def _load(self, customers: tuple[Customer, ...]) -> None:
        self.db.executemany(
            "INSERT INTO customers (customer_id, name, email, phone, city, created_at, record) VALUES (?,?,?,?,?,?,?)",
            [
                (c.customer_id, c.name, c.email, c.phone, c.city, c.created_at, c.model_dump_json())
                for c in customers
            ],
        )
        self.db.commit()

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        record = json.loads(row["record"])
        record["address_provenance"] = row["address_provenance"]
        return record

    def get(
        self, customer_id: str | None = None, email: str | None = None, phone: str | None = None
    ) -> dict | None:
        if customer_id:
            row = self.db.execute("SELECT * FROM customers WHERE customer_id = ?", (customer_id,)).fetchone()
        elif email:
            row = self.db.execute(
                "SELECT * FROM customers WHERE lower(email) = lower(?)", (email.strip(),)
            ).fetchone()
        elif phone:
            row = self.db.execute("SELECT * FROM customers WHERE phone = ?", (phone.strip(),)).fetchone()
        else:
            return None
        return self._row(row) if row else None

    def search(self, query: str = "", city: str | None = None, limit: int = 10) -> list[dict]:
        sql = "SELECT * FROM customers WHERE (name LIKE ? OR email LIKE ?)"
        params: list[Any] = [f"%{query}%", f"%{query}%"]
        if city:
            sql += " AND city LIKE ?"
            params.append(f"%{city}%")
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, min(int(limit), 100)))
        return [self._row(r) for r in self.db.execute(sql, params).fetchall()]

    def update_address(self, customer_id: str, new_address: str) -> dict | None:
        row = self.db.execute("SELECT record FROM customers WHERE customer_id = ?", (customer_id,)).fetchone()
        if not row:
            return None
        record = json.loads(row["record"])
        record["address"] = new_address
        self.db.execute(
            "UPDATE customers SET record = ?, address_provenance = 'customer_supplied' WHERE customer_id = ?",
            (json.dumps(record, ensure_ascii=False), customer_id),
        )
        self.db.commit()
        return self.get(customer_id=customer_id)

    def all(self) -> list[dict]:
        return [
            self._row(r) for r in self.db.execute("SELECT * FROM customers ORDER BY customer_id").fetchall()
        ]

    def verified_recipients(self) -> dict[str, str]:
        """Map every verified UPI / account / email to its customer id (used for destination trust)."""
        out: dict[str, str] = {}
        for c in self.all():
            for key in ("verified_upi", "verified_account", "email"):
                out[c[key].lower()] = c["customer_id"]
        return out
