from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Availability = Literal["available", "out_of_stock", "unknown"]
AlertKind = Literal["new", "restocked", "stock_increase"]


@dataclass(frozen=True)
class Listing:
    item_id: str
    title: str
    url: str
    price: str | None
    availability: Availability
    available_quantity: int | None = None


@dataclass(frozen=True)
class Alert:
    kind: AlertKind
    listing: Listing
    previous_quantity: int | None = None
