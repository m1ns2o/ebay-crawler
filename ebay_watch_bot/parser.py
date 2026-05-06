from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from .models import Availability, Listing

ITEM_ID_PATTERNS = (
    re.compile(r"/itm/(?:[^/?#]+/)?(\d{9,})"),
    re.compile(r"[?&](?:item|itemId|itm)=(\d{9,})"),
)

OUT_OF_STOCK_PATTERNS = (
    "out of stock",
    "sold out",
    "currently unavailable",
    "no longer available",
    "this listing has ended",
)

NO_RESULTS_PATTERNS = (
    "no exact matches found",
    "we couldn't find any exact matches",
    "0 results for",
    "didn't find any results",
)


class ParseError(RuntimeError):
    pass


def parse_search_results(html: str, *, base_url: str = "https://www.ebay.com") -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    listings: dict[str, Listing] = {}

    for item in _select_result_cards(soup):
        listing = _parse_listing(item, base_url=base_url)
        if listing is None:
            continue
        listings[listing.item_id] = listing

    return list(listings.values())


def describe_search_page(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else "unknown"
    return (
        f"title={title!r}, "
        f"s_item_count={len(soup.select('li.s-item'))}, "
        f"s_card_count={len(soup.select('li.s-card'))}, "
        f"itm_link_count={len(soup.select('a[href*=itm]'))}, "
        f"blocked={page_looks_blocked(html)}, "
        f"no_results={page_has_no_results(html)}"
    )


def page_has_no_results(html: str) -> bool:
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True).casefold()
    return any(pattern in text for pattern in NO_RESULTS_PATTERNS)


def page_looks_blocked(html: str) -> bool:
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True).casefold()
    return any(
        pattern in text
        for pattern in (
            "pardon our interruption",
            "verify yourself",
            "robot check",
            "captcha",
            "access denied",
            "중단이 발생하여 죄송합니다",
        )
    )


def _select_result_cards(soup: BeautifulSoup) -> list[Tag]:
    cards: list[Tag] = []
    for container in soup.select(".srp-results, .srp-river-results"):
        for item in container.select(":scope > li.s-item, :scope > li.s-card"):
            if isinstance(item, Tag):
                cards.append(item)

    if not cards:
        for item in soup.select("li.s-item, li.s-card"):
            if isinstance(item, Tag):
                cards.append(item)

    return cards


def _parse_listing(item: Tag, *, base_url: str) -> Listing | None:
    link = _extract_link(item, base_url=base_url)
    if not link:
        return None

    item_id = _extract_item_id(link)
    if not item_id:
        return None

    title = _extract_title(item)
    if not title or title.casefold() in {"shop on ebay", "explore related searches"}:
        return None

    text = item.get_text(" ", strip=True)
    availability = _extract_availability(text)
    quantity = _extract_quantity(text, availability=availability)

    return Listing(
        item_id=item_id,
        title=title,
        url=f"https://www.ebay.com/itm/{item_id}",
        price=_extract_price(item),
        availability=availability,
        available_quantity=quantity,
    )


def _extract_link(item: Tag, *, base_url: str) -> str | None:
    preferred_links = item.select("a.s-item__link[href], a.s-card__link[href]")
    candidates = [*preferred_links, *item.select("a[href]")]
    for candidate in candidates:
        if not isinstance(candidate, Tag):
            continue
        href = candidate.get("href")
        if isinstance(href, str) and ("/itm/" in href or "itm=" in href or "itemId=" in href):
            return urljoin(base_url, href)
    return None


def _extract_item_id(url: str) -> str | None:
    for pattern in ITEM_ID_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)
    return None


def _extract_title(item: Tag) -> str | None:
    title_node = item.select_one(".s-item__title, .s-card__title")
    if title_node is None:
        return None
    text_nodes = title_node.select(".su-styled-text")
    title = next(
        (
            node.get_text(" ", strip=True)
            for node in text_nodes
            if node.get_text(" ", strip=True)
        ),
        title_node.get_text(" ", strip=True),
    )
    title = _clean_title(title)
    return title or None


def _extract_price(item: Tag) -> str | None:
    price_node = item.select_one(".s-item__price, .s-card__price")
    if price_node is None:
        return None
    price = price_node.get_text(" ", strip=True)
    return price or None


def _clean_title(title: str) -> str:
    title = re.sub(r"^New Listing\s+", "", title, flags=re.IGNORECASE).strip()
    title = re.sub(r"\s+Opens in a new window or tab$", "", title, flags=re.IGNORECASE).strip()
    return title


def _extract_availability(text: str) -> Availability:
    normalized = text.casefold()
    if any(pattern in normalized for pattern in OUT_OF_STOCK_PATTERNS):
        return "out_of_stock"
    return "available"


def _extract_quantity(text: str, *, availability: Availability) -> int | None:
    if availability == "out_of_stock":
        return 0

    normalized = text.replace(",", "")
    match = re.search(r"(\d+)\s+available", normalized, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))

    if re.search(r"more than\s+(\d+)\s+available", normalized, flags=re.IGNORECASE):
        match = re.search(r"more than\s+(\d+)\s+available", normalized, flags=re.IGNORECASE)
        if match:
            return int(match.group(1)) + 1

    return None
