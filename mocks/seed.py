"""Write the deterministic demo dataset to ./data for inspection (CRM SQLite + inbox JSON).

Runtime Worlds build their own in-memory copies from the same seed, so this
file is informational: it lets judges open the CRM in any SQLite browser.
"""

from __future__ import annotations

import json
import sqlite3

from kavach.config import settings
from mocks.crm.store import CRM
from mocks.email.inbox import default_inbox


def main() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    crm_path = settings.data_dir / "crm.db"
    crm_path.unlink(missing_ok=True)
    source = CRM()
    with sqlite3.connect(crm_path) as target:
        source.db.backup(target)
    inbox = [m.model_dump() | {"body_text": m.body_text} for m in default_inbox()]
    (settings.data_dir / "inbox.json").write_text(
        json.dumps(inbox, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"seeded {len(source.all())} customers -> {crm_path}, {len(inbox)} tickets -> inbox.json")


if __name__ == "__main__":
    main()
