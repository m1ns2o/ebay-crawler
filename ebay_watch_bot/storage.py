from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .models import Listing


class Store:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.database_path)
        self.connection.row_factory = sqlite3.Row
        self._initialize()

    def close(self) -> None:
        self.connection.close()

    def is_initialized(self) -> bool:
        row = self.connection.execute(
            "SELECT value FROM metadata WHERE key = 'baseline_completed'"
        ).fetchone()
        return row is not None and row["value"] == "1"

    def mark_initialized(self) -> None:
        self.connection.execute(
            """
            INSERT INTO metadata(key, value)
            VALUES('baseline_completed', '1')
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """
        )
        self.connection.commit()

    def get_items(self) -> dict[str, dict[str, Any]]:
        rows = self.connection.execute("SELECT * FROM items").fetchall()
        return {row["item_id"]: dict(row) for row in rows}

    def upsert_listing(
        self,
        listing: Listing,
        *,
        now: str,
        notified_at: str | None = None,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO items(
                item_id, title, url, price, availability, available_quantity,
                first_seen_at, last_seen_at, notified_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(item_id) DO UPDATE SET
                title = excluded.title,
                url = excluded.url,
                price = excluded.price,
                availability = excluded.availability,
                available_quantity = excluded.available_quantity,
                last_seen_at = excluded.last_seen_at,
                notified_at = COALESCE(excluded.notified_at, items.notified_at)
            """,
            (
                listing.item_id,
                listing.title,
                listing.url,
                listing.price,
                listing.availability,
                listing.available_quantity,
                now,
                now,
                notified_at,
            ),
        )

    def mark_missing_as_out_of_stock(self, current_item_ids: Iterable[str], *, now: str) -> None:
        current_item_ids = set(current_item_ids)
        if not current_item_ids:
            self.connection.execute(
                """
                UPDATE items
                SET availability = 'out_of_stock',
                    available_quantity = 0,
                    last_seen_at = ?
                WHERE availability != 'out_of_stock'
                """,
                (now,),
            )
            return

        placeholders = ",".join("?" for _ in current_item_ids)
        self.connection.execute(
            f"""
            UPDATE items
            SET availability = 'out_of_stock',
                available_quantity = 0,
                last_seen_at = ?
            WHERE availability != 'out_of_stock'
              AND item_id NOT IN ({placeholders})
            """,
            (now, *current_item_ids),
        )

    def commit(self) -> None:
        self.connection.commit()

    def _initialize(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                item_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                price TEXT,
                availability TEXT NOT NULL,
                available_quantity INTEGER,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                notified_at TEXT
            )
            """
        )
        self.connection.commit()
