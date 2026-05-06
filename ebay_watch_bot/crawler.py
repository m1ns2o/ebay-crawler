from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Protocol

from .models import Alert, Listing
from .notifier import TelegramNotifier
from .parser import (
    ParseError,
    describe_search_page,
    page_has_no_results,
    page_looks_blocked,
    parse_search_results,
)
from .storage import Store

logger = logging.getLogger(__name__)


class FetchError(RuntimeError):
    pass


class Fetcher(Protocol):
    def fetch(self) -> str:
        pass


class Notifier(Protocol):
    def send_alert(self, alert: Alert, *, detected_at: datetime) -> None:
        pass


class EbayHtmlFetcher:
    def __init__(
        self,
        *,
        target_url: str,
        user_agent: str,
        ebay_cookie: str | None = None,
        timeout_seconds: int = 20,
    ) -> None:
        self.target_url = target_url
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds

    def fetch(self) -> str:
        try:
            from playwright.sync_api import (
                TimeoutError as PlaywrightTimeoutError,
                sync_playwright,
            )
        except ImportError as exc:
            raise FetchError(
                "Playwright is required for eBay HTML fetching. "
                "Install it with `pip install -r requirements.txt` and "
                "`python -m playwright install chromium`."
            ) from exc

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                context = browser.new_context(
                    user_agent=self.user_agent,
                    viewport={"width": 1920, "height": 1080},
                    locale="en-US",
                )
                page = context.new_page()

                try:
                    page.goto(
                        "https://www.ebay.com/",
                        wait_until="domcontentloaded",
                        timeout=self.timeout_seconds * 1000,
                    )
                    page.wait_for_timeout(2000)
                    response = page.goto(
                        self.target_url,
                        wait_until="domcontentloaded",
                        timeout=self.timeout_seconds * 1000,
                    )
                    page.wait_for_selector(
                        "li.s-item, li.s-card, .srp-results, .srp-river-results, body",
                        timeout=min(self.timeout_seconds * 1000, 10000),
                    )
                    try:
                        page.wait_for_load_state("networkidle", timeout=5000)
                    except PlaywrightTimeoutError:
                        logger.debug("Timed out waiting for network idle; continuing with DOM content")
                except PlaywrightTimeoutError as exc:
                    raise FetchError(f"Playwright timed out fetching eBay: {exc}") from exc

                content = page.content()

                if response and response.status in {403, 429}:
                    raise FetchError(f"eBay returned HTTP {response.status}; blocked or rate limited")
                if response and response.status >= 400:
                    raise FetchError(f"eBay returned HTTP {response.status}")
                if page_looks_blocked(content):
                    raise FetchError("eBay page appears to be blocked by bot/captcha protection")

                return content
            finally:
                browser.close()


class Watcher:
    def __init__(
        self,
        *,
        store: Store,
        fetcher: Fetcher,
        notifier: Notifier | TelegramNotifier | None,
        dry_run: bool = False,
    ) -> None:
        self.store = store
        self.fetcher = fetcher
        self.notifier = notifier
        self.dry_run = dry_run

    def check_once(self) -> list[Alert]:
        html = self.fetcher.fetch()
        listings = parse_search_results(html)

        if not listings and not page_has_no_results(html):
            raise ParseError(
                "No eBay listings were parsed and the page is not a no-results page: "
                f"{describe_search_page(html)}"
            )

        now = datetime.now(UTC)
        now_iso = now.isoformat()
        initialized = self.store.is_initialized()
        previous_items = self.store.get_items()
        alerts = [] if not initialized else detect_alerts(previous_items, listings)

        if not initialized:
            logger.info("Baseline run: storing %s listings without alerts", len(listings))
        else:
            logger.info("Detected %s alertable changes from %s listings", len(alerts), len(listings))
            self._send_alerts(alerts, detected_at=now)

        alerted_item_ids = {alert.listing.item_id for alert in alerts}
        for listing in listings:
            self.store.upsert_listing(
                listing,
                now=now_iso,
                notified_at=now_iso if listing.item_id in alerted_item_ids else None,
            )

        self.store.mark_missing_as_out_of_stock(
            (listing.item_id for listing in listings),
            now=now_iso,
        )
        if not initialized:
            self.store.mark_initialized()
        self.store.commit()

        return alerts

    def _send_alerts(self, alerts: list[Alert], *, detected_at: datetime) -> None:
        for alert in alerts:
            if self.dry_run:
                logger.info("DRY-RUN alert: %s %s", alert.kind, alert.listing.url)
                print_alert(alert, detected_at=detected_at)
                continue
            if self.notifier is None:
                raise RuntimeError("Notifier is required unless dry_run is enabled")
            self.notifier.send_alert(alert, detected_at=detected_at)


def detect_alerts(previous_items: dict[str, dict[str, object]], listings: list[Listing]) -> list[Alert]:
    alerts: list[Alert] = []

    for listing in listings:
        previous = previous_items.get(listing.item_id)
        if previous is None:
            alerts.append(Alert(kind="new", listing=listing))
            continue

        previous_availability = previous.get("availability")
        if previous_availability == "out_of_stock" and listing.availability == "available":
            alerts.append(Alert(kind="restocked", listing=listing))
            continue

        previous_quantity = previous.get("available_quantity")
        if (
            isinstance(previous_quantity, int)
            and listing.available_quantity is not None
            and listing.available_quantity > previous_quantity
            and previous_availability == "available"
            and listing.availability == "available"
        ):
            alerts.append(
                Alert(
                    kind="stock_increase",
                    listing=listing,
                    previous_quantity=previous_quantity,
                )
            )

    return alerts


def print_alert(alert: Alert, *, detected_at: datetime) -> None:
    from .notifier import compose_alert_message

    print(compose_alert_message(alert, detected_at=detected_at))
    print("-" * 60)
